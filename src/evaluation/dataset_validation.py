"""SafeRoute AI — Phase 42 dataset validation and freezing.

Design rules
------------
* A **missing** label file is an error, never an implicit negative.
* An **empty** label file is a valid negative image.
* Every ground-truth class must be one of the trained two-class set; unknown
  classes are rejected rather than silently ignored.
* Invalid boxes are rejected. Only sub-1% boundary rounding from center/size
  encoding is clamped to the image edge.
* A deterministic content hash covers every image and label file so an
  evaluation can be reproduced exactly.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml

from .matching import Box, BoxValidationError, GroundTruthBox, validate_bbox_norm

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CLASS_NAMES: Mapping[int, str] = {0: "pothole", 1: "crack"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
# Human annotations encode a box as center/size, so a boundary-touching hazard
# can round a few thousandths outside [0, 1]. Allow at most 1% of the image
# dimension and clamp it; anything larger is still rejected. Predictions use the
# strict 0.0 default because the serving detector already clips them.
LABEL_BOUNDARY_TOLERANCE = 0.01


class DatasetValidationError(ValueError):
    """Raised when the evaluation dataset is structurally invalid."""


class EmptyDatasetError(DatasetValidationError):
    """Raised when no evaluable images were found."""


class MissingAnnotationError(DatasetValidationError):
    """Raised when an image has no corresponding label file."""


@dataclass(frozen=True)
class LabelRecord:
    class_id: int
    class_name: str
    bbox_norm: Box


@dataclass(frozen=True)
class DatasetImage:
    image_id: str
    image_path: Path
    label_path: Path
    split: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def session_id(self) -> Optional[str]:
        value = self.metadata.get("session_id")
        return str(value) if value not in (None, "") else None

    @property
    def camera_id(self) -> Optional[str]:
        value = self.metadata.get("camera_id")
        return str(value) if value not in (None, "") else None

    @property
    def condition(self) -> str:
        value = self.metadata.get("condition")
        return str(value) if value not in (None, "") else "unlabelled"

    @property
    def route_id(self) -> Optional[str]:
        value = self.metadata.get("route_id")
        return str(value) if value not in (None, "") else None

    @property
    def segment_id(self) -> Optional[str]:
        value = self.metadata.get("segment_id")
        return str(value) if value not in (None, "") else None

    @property
    def distance_km(self) -> Optional[float]:
        value = self.metadata.get("distance_km")
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @property
    def segment_length_m(self) -> Optional[float]:
        value = self.metadata.get("segment_length_m")
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @property
    def sha256(self) -> Optional[str]:
        value = self.metadata.get("_sha256")
        return str(value) if value else None


@dataclass(frozen=True)
class DatasetInventory:
    dataset_yaml: Path
    dataset_root: Path
    class_names: Mapping[int, str]
    images: Tuple[DatasetImage, ...]
    ground_truth: Tuple[GroundTruthBox, ...]
    dataset_sha256: str
    image_sha256: str
    label_sha256: str
    manifest: Mapping[str, Any]
    provenance: Mapping[str, Any]
    annotation: Mapping[str, Any]
    quality_control: Mapping[str, Any]
    warnings: Tuple[str, ...]
    split: str

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def class_counts(self) -> Dict[str, int]:
        counts = Counter(box.class_name for box in self.ground_truth)
        return {name: int(counts.get(name, 0)) for name in self.class_names.values()}

    @property
    def positive_image_ids(self) -> Tuple[str, ...]:
        ids = {box.image_id for box in self.ground_truth}
        return tuple(image.image_id for image in self.images if image.image_id in ids)

    @property
    def negative_image_ids(self) -> Tuple[str, ...]:
        positives = set(self.positive_image_ids)
        return tuple(image.image_id for image in self.images if image.image_id not in positives)

    @property
    def sessions(self) -> Tuple[str, ...]:
        values = {image.session_id for image in self.images if image.session_id}
        return tuple(sorted(values))

    @property
    def missing_session_count(self) -> int:
        return sum(1 for image in self.images if not image.session_id)

    @property
    def conditions(self) -> Tuple[str, ...]:
        return tuple(sorted({image.condition for image in self.images}))

    @property
    def total_distance_km(self) -> Optional[float]:
        values = [image.distance_km for image in self.images if image.distance_km is not None]
        return float(sum(values)) if values else None

    def image_by_id(self) -> Dict[str, DatasetImage]:
        return {image.image_id: image for image in self.images}

    def ground_truth_by_image(self) -> Dict[str, List[GroundTruthBox]]:
        grouped: Dict[str, List[GroundTruthBox]] = {image.image_id: [] for image in self.images}
        for box in self.ground_truth:
            grouped.setdefault(box.image_id, []).append(box)
        return grouped

    def annotation_version(self) -> Optional[str]:
        value = self.annotation.get("version") or self.manifest.get("annotation_version")
        return str(value) if value not in (None, "") else None

    def dataset_version(self) -> Optional[str]:
        value = self.manifest.get("dataset_version") or self.manifest.get("version")
        return str(value) if value not in (None, "") else None


def compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _relative_key(path: Path, root: Path) -> str:
    """Stable dataset-relative path key; absolute only when outside the root."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _normalise_names(raw: Any) -> Dict[int, str]:
    if raw is None:
        return dict(DEFAULT_CLASS_NAMES)
    if isinstance(raw, Mapping):
        return {int(key): str(value) for key, value in raw.items()}
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return {index: str(value) for index, value in enumerate(raw)}
    raise DatasetValidationError(f"Unsupported 'names' entry in dataset yaml: {raw!r}")


def load_dataset_yaml(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise DatasetValidationError(f"Dataset yaml not found at {path}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise DatasetValidationError(f"Invalid dataset yaml {path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise DatasetValidationError(f"Dataset yaml {path} must contain a mapping")
    return data


def _candidate_roots(
    yaml_dir: Path,
    dataset_root: Path,
    workspace_root: Path,
) -> List[Path]:
    return [dataset_root, workspace_root, yaml_dir]


def _resolve_existing(raw: str, roots: Sequence[Path]) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        if candidate.exists():
            return candidate.resolve()
        raise DatasetValidationError(f"Dataset path does not exist: {candidate}")
    for root in roots:
        resolved = (root / candidate).resolve()
        if resolved.exists():
            return resolved
    raise DatasetValidationError(
        f"Dataset path {raw!r} not found relative to any of: "
        + ", ".join(str(root) for root in roots)
    )


def _images_in_directory(directory: Path) -> List[Path]:
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _expand_split_entry(
    entry: Any,
    roots: Sequence[Path],
) -> List[Path]:
    if isinstance(entry, Sequence) and not isinstance(entry, (str, bytes)):
        collected: List[Path] = []
        for item in entry:
            collected.extend(_expand_split_entry(item, roots))
        return collected

    if not isinstance(entry, str) or not entry.strip():
        raise DatasetValidationError(f"Invalid split entry: {entry!r}")

    resolved = _resolve_existing(entry.strip(), roots)
    if resolved.is_dir():
        return _images_in_directory(resolved)
    if resolved.suffix.lower() == ".txt":
        images: List[Path] = []
        for line_number, raw_line in enumerate(
            resolved.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                images.extend(_expand_split_entry(line, roots))
            except DatasetValidationError as exc:
                raise DatasetValidationError(
                    f"{resolved}:{line_number}: {exc}"
                ) from exc
        return images
    if resolved.suffix.lower() in IMAGE_EXTENSIONS:
        return [resolved]
    raise DatasetValidationError(f"Unsupported split entry file type: {resolved}")


def _label_candidates(image_path: Path, dataset_root: Path) -> List[Path]:
    candidates: List[Path] = []
    parts = list(image_path.parts)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index].lower() == "images":
            replaced = parts[:index] + ["labels"] + parts[index + 1 :]
            candidates.append(Path(*replaced).with_suffix(".txt"))
            break
    candidates.append(image_path.with_suffix(".txt"))
    try:
        relative = image_path.relative_to(dataset_root)
    except ValueError:
        relative = None
    if relative is not None:
        candidates.append(dataset_root / "labels" / relative.with_suffix(".txt"))
    return candidates


def _locate_label(image_path: Path, dataset_root: Path) -> Path:
    for candidate in _label_candidates(image_path, dataset_root):
        if candidate.is_file():
            return candidate
    raise MissingAnnotationError(
        f"No annotation file for image {image_path}. A missing label is not a "
        "negative image; add an empty label file for a verified negative."
    )


def parse_label_file(path: Path, class_names: Mapping[int, str]) -> Tuple[LabelRecord, ...]:
    """Parse a YOLO detection label file; reject anything malformed."""
    records: List[LabelRecord] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise DatasetValidationError(f"Label file is not UTF-8: {path}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 5:
            raise DatasetValidationError(
                f"{path}:{line_number}: expected 5 YOLO fields, got {len(fields)}"
            )
        try:
            class_id = int(fields[0])
        except ValueError as exc:
            raise DatasetValidationError(
                f"{path}:{line_number}: class id is not an integer: {fields[0]!r}"
            ) from exc
        if class_id not in class_names:
            raise DatasetValidationError(
                f"{path}:{line_number}: class id {class_id} is not a trained class "
                f"({sorted(class_names)}). Unsupported classes cannot be scored as hazards."
            )
        try:
            cx, cy, width, height = (float(value) for value in fields[1:])
        except ValueError as exc:
            raise DatasetValidationError(
                f"{path}:{line_number}: non-numeric coordinates"
            ) from exc
        if not all(math.isfinite(value) for value in (cx, cy, width, height)):
            raise DatasetValidationError(
                f"{path}:{line_number}: non-finite YOLO coordinates"
            )
        if width <= 0.0 or height <= 0.0:
            raise DatasetValidationError(
                f"{path}:{line_number}: YOLO width/height must be positive, got "
                f"width={width}, height={height}"
            )
        # YOLO stores normalized center-x, center-y, width, height. Convert to
        # corners so the rest of the harness works in [x1, y1, x2, y2].
        try:
            bbox = validate_bbox_norm(
                (
                    cx - width / 2.0,
                    cy - height / 2.0,
                    cx + width / 2.0,
                    cy + height / 2.0,
                ),
                label=f"{path.name}:{line_number}",
                boundary_tolerance=LABEL_BOUNDARY_TOLERANCE,
            )
        except BoxValidationError as exc:
            raise DatasetValidationError(f"{path}:{line_number}: {exc}") from exc
        records.append(
            LabelRecord(
                class_id=class_id,
                class_name=class_names[class_id],
                bbox_norm=bbox,
            )
        )
    return tuple(records)


def _validate_image_bytes(path: Path, raw: bytes) -> Tuple[int, int]:
    if not raw:
        raise DatasetValidationError(f"Image file is empty: {path}")
    try:
        import cv2
        import numpy as np
    except ImportError as exc:  # pragma: no cover - environment guarantees cv2
        raise DatasetValidationError(
            "OpenCV/numpy are required to validate evaluation images"
        ) from exc
    buffer = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise DatasetValidationError(f"Image cannot be decoded: {path}")
    height, width = image.shape[:2]
    if width <= 0 or height <= 0:
        raise DatasetValidationError(f"Image has invalid dimensions: {path}")
    return int(width), int(height)


def _load_manifest(manifest_path: Optional[Path], dataset_root: Path) -> Tuple[Mapping[str, Any], Path]:
    candidates: List[Path] = []
    if manifest_path is not None:
        candidates = [manifest_path]
    else:
        candidates = [
            dataset_root / "manifests" / "independent_manifest.json",
            dataset_root / "manifests" / "manifest.json",
            dataset_root / "manifest.json",
        ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                with open(candidate, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (json.JSONDecodeError, OSError) as exc:
                raise DatasetValidationError(f"Invalid manifest {candidate}: {exc}") from exc
            if not isinstance(data, Mapping):
                raise DatasetValidationError(f"Manifest {candidate} must be a JSON object")
            return data, candidate
    if manifest_path is not None:
        raise DatasetValidationError(f"Manifest not found at {manifest_path}")
    return {}, Path()


def _load_session_csv(dataset_root: Path) -> List[Dict[str, str]]:
    for candidate in [
        dataset_root / "manifests" / "collection_sessions.csv",
        dataset_root / "collection_sessions.csv",
    ]:
        if candidate.is_file():
            with open(candidate, "r", encoding="utf-8-sig", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
    return []


def _metadata_lookup(
    manifest: Mapping[str, Any],
    session_rows: Sequence[Mapping[str, str]],
) -> Dict[str, Mapping[str, Any]]:
    lookup: Dict[str, Mapping[str, Any]] = {}

    def register(entry: Mapping[str, Any]) -> None:
        keys: List[str] = []
        for key in ("file", "path", "image", "filename", "image_id", "stem"):
            value = entry.get(key)
            if value not in (None, ""):
                text = str(value).replace("\\", "/")
                keys.extend([text, Path(text).name, Path(text).stem])
        for key in keys:
            lookup.setdefault(key, entry)

    raw_images = manifest.get("images") or []
    if isinstance(raw_images, Sequence) and not isinstance(raw_images, (str, bytes)):
        for entry in raw_images:
            if isinstance(entry, Mapping):
                register(entry)
    for row in session_rows:
        register(row)
    return lookup


def _lookup_metadata(
    lookup: Mapping[str, Mapping[str, Any]],
    image_path: Path,
    dataset_root: Path,
    workspace_root: Path,
) -> Mapping[str, Any]:
    candidates: List[str] = []
    for root in (dataset_root, workspace_root):
        try:
            candidates.append(image_path.relative_to(root).as_posix())
        except ValueError:
            continue
    candidates.extend([image_path.name, image_path.stem])
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return {}


def collect_dataset(
    dataset_yaml: Path,
    *,
    manifest_path: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
    split: str = "test",
    validate_images: bool = True,
    require_session_metadata: bool = False,
) -> DatasetInventory:
    """Parse and validate an independent evaluation split.

    Raises ``EmptyDatasetError`` for an empty split and
    ``MissingAnnotationError`` for an unannotated image. All integrity problems
    are raised explicitly so an evaluation cannot silently proceed.
    """
    workspace = Path(workspace_root).resolve() if workspace_root else WORKSPACE_ROOT
    yaml_path = Path(dataset_yaml)
    if not yaml_path.is_absolute():
        yaml_path = (workspace / yaml_path).resolve()

    data = load_dataset_yaml(yaml_path)
    yaml_dir = yaml_path.parent
    raw_root = data.get("path")
    if raw_root in (None, ""):
        dataset_root = yaml_dir
    else:
        candidate_root = Path(str(raw_root))
        dataset_root = (
            candidate_root.resolve()
            if candidate_root.is_absolute()
            else (yaml_dir / candidate_root).resolve()
        )
    roots = _candidate_roots(yaml_dir, dataset_root, workspace)

    class_names = _normalise_names(data.get("names"))
    if split not in data:
        available = [key for key in ("test", "val", "train") if key in data]
        raise DatasetValidationError(
            f"Dataset yaml {yaml_path} has no '{split}' split "
            f"(available: {available or 'none'})"
        )

    image_paths = _expand_split_entry(data[split], roots)
    # De-duplicate while preserving deterministic order.
    seen_paths = set()
    unique_paths: List[Path] = []
    for path in image_paths:
        key = str(path.resolve())
        if key not in seen_paths:
            seen_paths.add(key)
            unique_paths.append(path.resolve())
    if not unique_paths:
        raise EmptyDatasetError(
            f"The '{split}' split of {yaml_path} contains no images. An empty "
            "evaluation cannot be reported as a successful evaluation."
        )

    manifest, manifest_source = _load_manifest(
        Path(manifest_path) if manifest_path else None,
        dataset_root,
    )
    session_rows = _load_session_csv(dataset_root)
    lookup = _metadata_lookup(manifest, session_rows)

    images: List[DatasetImage] = []
    ground_truth: List[GroundTruthBox] = []
    warnings: List[str] = []
    seen_ids: Dict[str, Path] = {}
    image_hashes: List[str] = []
    label_hashes: List[str] = []

    for image_path in unique_paths:
        label_path = _locate_label(image_path, dataset_root)
        raw = image_path.read_bytes()
        image_hash = hashlib.sha256(raw).hexdigest().upper()
        image_hashes.append(image_hash)

        metadata: Dict[str, Any] = dict(
            _lookup_metadata(lookup, image_path, dataset_root, workspace)
        )
        metadata.setdefault("file", image_path.as_posix())
        metadata["_sha256"] = image_hash
        metadata["_label_path"] = label_path.as_posix()

        if validate_images:
            width, height = _validate_image_bytes(image_path, raw)
            metadata.setdefault("width", width)
            metadata.setdefault("height", height)

        label_raw = label_path.read_bytes()
        label_hashes.append(hashlib.sha256(label_raw).hexdigest().upper())
        label_records = parse_label_file(label_path, class_names)

        image_id = str(metadata.get("image_id") or image_path.stem)
        if image_id in seen_ids:
            raise DatasetValidationError(
                f"Duplicate image_id '{image_id}' for {image_path} and {seen_ids[image_id]}"
            )
        seen_ids[image_id] = image_path

        if not metadata.get("session_id"):
            # Common alternate names in collection manifests.
            for alias in ("capture_session", "clip_id", "video_id", "route_session"):
                if metadata.get(alias) not in (None, ""):
                    metadata["session_id"] = str(metadata[alias])
                    break

        image = DatasetImage(
            image_id=image_id,
            image_path=image_path,
            label_path=label_path,
            split=split,
            metadata=metadata,
        )
        images.append(image)

        if require_session_metadata and not image.session_id:
            raise DatasetValidationError(
                f"Image {image_id} has no session_id. Independent evaluation must "
                "be grouped by collection session to prevent adjacent-frame leakage."
            )

        for record in label_records:
            ground_truth.append(
                GroundTruthBox(
                    image_id=image_id,
                    class_name=record.class_name,
                    bbox_norm=record.bbox_norm,
                    session_id=image.session_id,
                    condition=image.condition,
                    route_id=image.route_id,
                    segment_id=image.segment_id,
                    image_path=image_path.as_posix(),
                )
            )

    if not ground_truth:
        warnings.append(
            "The evaluation split contains no annotated hazards (all negatives). "
            "Recall and AP are undefined; only false-positive behaviour can be measured."
        )

    unmatched_manifest_images = 0
    raw_images = manifest.get("images") or []
    if isinstance(raw_images, Sequence) and not isinstance(raw_images, (str, bytes)):
        matched_ids = {image.image_id for image in images}
        for entry in raw_images:
            if isinstance(entry, Mapping) and entry.get("image_id") not in matched_ids:
                unmatched_manifest_images += 1
    if unmatched_manifest_images:
        warnings.append(
            f"{unmatched_manifest_images} manifest image entrie(s) do not correspond "
            "to images in the evaluated split."
        )

    dataset_hash_material = "\n".join(
        sorted(
            f"images/{_relative_key(image_path, dataset_root)}\t{hash_value}"
            for image_path, hash_value in zip(unique_paths, image_hashes)
        )
        + sorted(
            f"labels/{_relative_key(image.label_path, dataset_root)}\t{hash_value}"
            for image, hash_value in zip(images, label_hashes)
        )
    )
    dataset_sha256 = hashlib.sha256(dataset_hash_material.encode("utf-8")).hexdigest().upper()
    image_sha256 = hashlib.sha256(
        "\n".join(sorted(image_hashes)).encode("utf-8")
    ).hexdigest().upper()
    label_sha256 = hashlib.sha256(
        "\n".join(sorted(label_hashes)).encode("utf-8")
    ).hexdigest().upper()

    provenance = manifest.get("provenance") or manifest.get("source") or {}
    annotation = manifest.get("annotation") or {}
    quality_control = manifest.get("quality_control") or manifest.get("qc") or {}
    if not provenance:
        warnings.append(
            "No collection provenance recorded in the dataset manifest; "
            "independence cannot be established."
        )
    if not annotation:
        warnings.append(
            "No annotation policy/version recorded in the dataset manifest; "
            "annotation reliability cannot be established."
        )

    return DatasetInventory(
        dataset_yaml=yaml_path,
        dataset_root=dataset_root,
        class_names=class_names,
        images=tuple(images),
        ground_truth=tuple(ground_truth),
        dataset_sha256=dataset_sha256,
        image_sha256=image_sha256,
        label_sha256=label_sha256,
        manifest=manifest,
        provenance=provenance,
        annotation=annotation,
        quality_control=quality_control,
        warnings=tuple(warnings + ([f"Manifest loaded from {manifest_source}"] if manifest_source else [])),
        split=split,
    )


def summarise_inventory(inventory: DatasetInventory) -> Dict[str, object]:
    """JSON-safe summary for the evaluation report."""
    return {
        "dataset_yaml": str(inventory.dataset_yaml),
        "dataset_root": str(inventory.dataset_root),
        "split": inventory.split,
        "dataset_version": inventory.dataset_version(),
        "annotation_version": inventory.annotation_version(),
        "dataset_sha256": inventory.dataset_sha256,
        "image_sha256": inventory.image_sha256,
        "label_sha256": inventory.label_sha256,
        "image_count": inventory.image_count,
        "positive_image_count": len(inventory.positive_image_ids),
        "negative_image_count": len(inventory.negative_image_ids),
        "ground_truth_count": len(inventory.ground_truth),
        "class_counts": inventory.class_counts,
        "class_names": {str(key): value for key, value in inventory.class_names.items()},
        "session_count": len(inventory.sessions),
        "missing_session_count": inventory.missing_session_count,
        "condition_counts": dict(
            Counter(image.condition for image in inventory.images)
        ),
        "total_distance_km": inventory.total_distance_km,
        "provenance": dict(inventory.provenance),
        "annotation": dict(inventory.annotation),
        "quality_control": dict(inventory.quality_control),
        "warnings": list(inventory.warnings),
    }


__all__ = [
    "DEFAULT_CLASS_NAMES",
    "DatasetImage",
    "DatasetInventory",
    "DatasetValidationError",
    "EmptyDatasetError",
    "LABEL_BOUNDARY_TOLERANCE",
    "LabelRecord",
    "MissingAnnotationError",
    "collect_dataset",
    "compute_file_sha256",
    "load_dataset_yaml",
    "parse_label_file",
    "summarise_inventory",
]
