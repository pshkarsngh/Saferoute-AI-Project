"""P3 — dataset validation, freeze and content hashing.

A freeze is refused when any structural, provenance, geometry, session or
annotation-review check fails. When it succeeds, the generated manifest is
exactly what the Phase 42 harness reads: ``provenance``, ``annotation``,
``quality_control`` and per-image session metadata.

The freeze is a content hash, not a cryptographic signature. The manifest says
so explicitly instead of implying a signing key was used.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml

from ..evaluation.dataset_validation import (
    DatasetValidationError,
    MissingAnnotationError,
    compute_file_sha256,
    parse_label_file,
)
from .acquisition import (
    AcquisitionRecord,
    load_acquisition_csv,
    validate_acquisition,
)
from .annotation import (
    AnnotationAudit,
    load_adjudication_csv,
    load_review_csv,
    validate_annotation_evidence,
)
from .common import (
    ACQUISITION_COLUMNS,
    CLASS_NAMES,
    COLLECTION_SESSION_COLUMNS,
    FreezeStatus,
    SPLITS,
    TOOL_VERSION,
    git_commit,
    list_images,
    relative_posix,
    sha256_file,
    sha256_text,
    utc_now,
)
from .reference import ReferenceRegistry, load_reference_registry
from .sources import SourceRecord
from .splitting import validate_session_atomicity


class FreezeError(ValueError):
    """Raised when the dataset cannot be read well enough to freeze."""


@dataclass(frozen=True)
class FreezeResult:
    status: FreezeStatus
    errors: Tuple[str, ...]
    warnings: Tuple[str, ...]
    dataset_root: str
    dataset_version: str
    annotation_version: str
    written: bool
    outputs: Mapping[str, str]
    acquisition: Mapping[str, Any]
    annotation: Mapping[str, Any]
    leakage: Mapping[str, Any]
    hashes: Mapping[str, Any]
    split_counts: Mapping[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "dataset_root": self.dataset_root,
            "dataset_version": self.dataset_version,
            "annotation_version": self.annotation_version,
            "frozen": self.written and self.status in {FreezeStatus.PASS, FreezeStatus.CONDITIONAL},
            "written": self.written,
            "outputs": dict(self.outputs),
            "split_counts": dict(self.split_counts),
            "acquisition": dict(self.acquisition),
            "annotation": dict(self.annotation),
            "leakage": dict(self.leakage),
            "hashes": dict(self.hashes),
        }


def _label_path_for(image_path: Path, root: Path) -> Path:
    relative = image_path.relative_to(root)
    parts = list(relative.parts)
    parts[0] = "labels"
    return (root / Path(*parts)).with_suffix(".txt")


def _hash_records(root: Path) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    per_split: Dict[str, Dict[str, Any]] = {}
    all_image_hashes: List[str] = []
    all_label_hashes: List[str] = []
    block_hashes: List[str] = []

    for split in SPLITS:
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        images = list_images(image_dir)
        image_entries = []
        label_entries = []
        for image_path in images:
            rel = relative_posix(image_path, root)
            digest = sha256_file(image_path)
            image_entries.append((rel, digest))
            all_image_hashes.append(digest)
            label_path = _label_path_for(image_path, root)
            if label_path.is_file():
                label_rel = relative_posix(label_path, root)
                label_digest = sha256_file(label_path)
                label_entries.append((label_rel, label_digest))
                all_label_hashes.append(label_digest)
        # Match the Phase 42 `collect_dataset` hash material exactly. It prefixes
        # "images/" and "labels/" to the dataset-relative path, so an image at
        # images/test/a.jpg contributes "images/images/test/a.jpg".
        image_lines = [f"images/{rel}\t{digest}" for rel, digest in image_entries]
        label_lines = [f"labels/{rel}\t{digest}" for rel, digest in label_entries]
        combined_material = "\n".join(sorted(image_lines) + sorted(label_lines))
        per_split[split] = {
            "image_count": len(image_entries),
            "label_count": len(label_entries),
            "image_sha256": sha256_text("\n".join(sorted(d for _, d in image_entries))),
            "label_sha256": sha256_text("\n".join(sorted(d for _, d in label_entries))),
            "dataset_sha256": sha256_text(combined_material),
        }
        block_hashes.append(f"{split}\t{per_split[split]['dataset_sha256']}")

    hashes = {
        "algorithm": "sha256",
        "combined_sha256": sha256_text("\n".join(block_hashes)),
        "image_sha256": sha256_text("\n".join(sorted(all_image_hashes))),
        "label_sha256": sha256_text("\n".join(sorted(all_label_hashes))),
        "per_split": per_split,
    }
    return hashes, per_split


def compute_dataset_hashes(root: Path) -> Dict[str, Any]:
    root = Path(root)
    hashes, _ = _hash_records(root)
    files: List[Dict[str, Any]] = []
    for split in SPLITS:
        for path in list_images(root / "images" / split):
            label_path = _label_path_for(path, root)
            files.append(
                {
                    "path": relative_posix(path, root),
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )
            if label_path.is_file():
                files.append(
                    {
                        "path": relative_posix(label_path, root),
                        "sha256": sha256_file(label_path),
                        "size_bytes": label_path.stat().st_size,
                    }
                )
    for name in (
        "manifests/acquisition_manifest.csv",
        "manifests/collection_sessions.csv",
        "manifests/annotation_review.csv",
        "manifests/adjudication.csv",
        "manifests/training_sessions.csv",
    ):
        path = root / name
        if path.is_file():
            files.append(
                {
                    "path": name,
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    hashes["files"] = sorted(files, key=lambda item: item["path"])
    return hashes


def _read_rows(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _dataset_yaml_text() -> str:
    payload = {
        "path": ".",
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {0: "pothole", 1: "crack"},
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def _capture_range(records: Sequence[AcquisitionRecord]) -> List[str]:
    dates = sorted({record.capture_date for record in records if record.capture_date})
    if not dates:
        return []
    return [dates[0], dates[-1]]


def _session_rows(records: Sequence[AcquisitionRecord]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for record in records:
        entry = grouped.setdefault(
            record.capture_session_id,
            {
                "session_id": record.capture_session_id,
                "source_ids": set(),
                "camera_ids": set(),
                "capture_dates": set(),
                "countries": set(),
                "regions": set(),
                "route_ids": set(),
                "splits": set(),
                "image_count": 0,
            },
        )
        entry["source_ids"].add(record.source_id)
        entry["camera_ids"].add(record.camera_id)
        entry["capture_dates"].add(record.capture_date)
        entry["countries"].add(record.country)
        entry["regions"].add(record.region)
        if record.route_id:
            entry["route_ids"].add(record.route_id)
        entry["splits"].add(record.split)
        entry["image_count"] += 1

    rows: List[Dict[str, Any]] = []
    for session_id, entry in sorted(grouped.items()):
        rows.append(
            {
                "session_id": session_id,
                "source_id": ";".join(sorted(entry["source_ids"])),
                "camera_id": ";".join(sorted(entry["camera_ids"])),
                "capture_date": ";".join(sorted(entry["capture_dates"])),
                "country": ";".join(sorted(entry["countries"])),
                "region": ";".join(sorted(entry["regions"])),
                "route_id": ";".join(sorted(entry["route_ids"])),
                "image_count": entry["image_count"],
                "split": "|".join(sorted(entry["splits"])),
            }
        )
    return rows


def freeze_dataset(
    root: Path,
    *,
    sources: Mapping[str, SourceRecord],
    dataset_version: str,
    annotation_version: str,
    frozen_by: str,
    policy_path: Path,
    reference_registry_path: Optional[Path] = None,
    reference_image_paths: Sequence[Path] = (),
    write: bool = True,
    max_hamming_distance: int = 8,
) -> FreezeResult:
    root = Path(root).resolve()
    errors: List[str] = []
    warnings: List[str] = []
    outputs: Dict[str, str] = {}

    if not root.is_dir():
        raise FreezeError(f"Dataset root does not exist: {root}")
    if not str(frozen_by or "").strip():
        errors.append("frozen_by is empty")
    if not str(dataset_version or "").strip():
        errors.append("dataset_version is empty")
    if not str(annotation_version or "").strip():
        errors.append("annotation_version is empty")

    policy = Path(policy_path)
    if not policy.is_file():
        errors.append(f"annotation policy/guideline not found: {policy}")
        policy_sha = None
    else:
        policy_sha = sha256_file(policy)

    acquisition_csv = root / "manifests" / "acquisition_manifest.csv"
    review_csv = root / "manifests" / "annotation_review.csv"
    adjudication_csv = root / "manifests" / "adjudication.csv"
    for path, label in (
        (acquisition_csv, "acquisition manifest"),
        (review_csv, "annotation review"),
        (adjudication_csv, "adjudication"),
    ):
        if not path.is_file():
            errors.append(f"{label} not found: {path}")

    if errors:
        return FreezeResult(
            status=FreezeStatus.FAIL,
            errors=tuple(errors),
            warnings=tuple(warnings),
            dataset_root=str(root),
            dataset_version=dataset_version,
            annotation_version=annotation_version,
            written=False,
            outputs={},
            acquisition={},
            annotation={},
            leakage={},
            hashes={},
            split_counts={split: 0 for split in SPLITS},
        )

    records, _ = load_acquisition_csv(acquisition_csv)
    acquisition_audit = validate_acquisition(
        records,
        sources=sources,
        images_root=root,
        require_layout=True,
        check_files=True,
        reference_image_paths=reference_image_paths,
        max_hamming_distance=max_hamming_distance,
    )
    errors.extend(acquisition_audit.errors)
    warnings.extend(acquisition_audit.warnings)
    errors.extend(validate_session_atomicity(records))

    expected_images: List[str] = []
    label_counts: Dict[str, int] = {}
    split_by_image: Dict[str, str] = {}
    split_counts = {split: 0 for split in SPLITS}
    for split in SPLITS:
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        if not image_dir.is_dir():
            errors.append(f"missing split directory: {image_dir}")
        if not label_dir.is_dir():
            errors.append(f"missing split directory: {label_dir}")
        images = list_images(image_dir)
        split_counts[split] = len(images)
        for image_path in images:
            image_id = image_path.stem
            expected_images.append(image_id)
            split_by_image[image_id] = split
            label_path = _label_path_for(image_path, root)
            if not label_path.is_file():
                errors.append(
                    f"image {image_id!r} has no label file; a missing label is not "
                    "a verified negative"
                )
                label_counts[image_id] = 0
                continue
            try:
                label_records = parse_label_file(label_path, CLASS_NAMES)
            except (DatasetValidationError, MissingAnnotationError) as exc:
                errors.append(f"image {image_id!r}: invalid annotation: {exc}")
                label_counts[image_id] = 0
                continue
            label_counts[image_id] = len(label_records)

    if not expected_images:
        errors.append("No evaluation images were found in images/{train,val,test}")
    if split_counts.get("test", 0) == 0:
        errors.append("The locked test split contains no images")

    review_rows, _ = load_review_csv(review_csv)
    adjudication_rows, _ = load_adjudication_csv(adjudication_csv)
    annotation_audit: AnnotationAudit = validate_annotation_evidence(
        review_rows,
        adjudication_rows,
        expected_annotation_version=annotation_version,
        label_counts=label_counts,
        split_by_image=split_by_image,
        expected_images=expected_images,
    )
    errors.extend(annotation_audit.errors)
    warnings.extend(annotation_audit.warnings)

    reference: Optional[ReferenceRegistry] = None
    if reference_registry_path is not None:
        try:
            reference = load_reference_registry(Path(reference_registry_path))
        except Exception as exc:  # ReferenceRegistryError is a ValueError
            errors.append(f"reference registry error: {exc}")
    else:
        default_reference = root / "manifests" / "training_sessions.csv"
        if default_reference.is_file():
            try:
                reference = load_reference_registry(default_reference)
            except ValueError as exc:
                errors.append(f"reference registry error: {exc}")
        else:
            warnings.append(
                "No reference-session registry supplied; separation from training "
                "sessions is unproven."
            )

    leakage: Dict[str, Any] = {
        "reference_registry_present": reference is not None,
        "reference_registry_verified": bool(reference and reference.verified),
        "reference_registry_quality": reference.quality if reference else None,
        "reference_session_count": reference.session_count if reference else 0,
        "reference_image_count": reference.image_count if reference else 0,
        "session_overlap": [],
        "exact_duplicate_groups": [list(group) for group in acquisition_audit.duplicate_hash_groups],
        "reference_exact_match_count": len(acquisition_audit.reference_exact_matches),
        "reference_near_match_count": len(acquisition_audit.reference_near_matches),
    }
    if reference is not None:
        independent_sessions = {record.capture_session_id for record in records}
        overlap = sorted(independent_sessions & set(reference.session_ids()))
        leakage["session_overlap"] = overlap
        if overlap:
            errors.append(
                f"independent sessions overlap reference sessions: {overlap}"
            )
        if reference.errors:
            errors.extend(f"reference registry: {item}" for item in reference.errors)
        if reference.proxy_only:
            warnings.append(
                "Reference registry is proxy-only (filename-derived dates); "
                "session/camera/route separation is not proven."
            )
        warnings.extend(reference.warnings)
    if not reference_image_paths:
        warnings.append(
            "No reference imagery was supplied; cross-corpus exact/perceptual "
            "duplicate checking is incomplete."
        )

    if not annotation_audit.verified_negative_ids and any(
        count == 0 for count in label_counts.values()
    ):
        warnings.append(
            "The dataset contains empty label files but no adjudicated verified "
            "negatives; this should be impossible and is reported."
        )

    positive_test_images = sum(1 for image_id, count in label_counts.items() if split_by_image.get(image_id) == "test" and count > 0)
    if split_counts.get("test", 0) and positive_test_images == 0:
        warnings.append(
            "The locked test split has no annotated hazards; AP/recall will be "
            "undefined and only false-positive behaviour can be measured."
        )

    # ------------------------------------------------------------------ status
    if errors:
        status = FreezeStatus.FAIL
    elif reference is None or reference.proxy_only:
        status = FreezeStatus.NOT_ASSESSED
    elif warnings:
        status = FreezeStatus.CONDITIONAL
    else:
        status = FreezeStatus.PASS

    hashes = compute_dataset_hashes(root)
    acquisition_summary = {
        "image_count": len(records),
        "session_count": acquisition_audit.session_count,
        "split_counts": dict(split_counts),
        "source_ids": sorted({record.source_id for record in records}),
        "licences": sorted({record.licence_id for record in records}),
        "permission_evidence": sorted({record.licence_evidence for record in records}),
        "capture_date_range": _capture_range(records),
        "countries": sorted({record.country for record in records if record.country}),
        "regions": sorted({record.region for record in records if record.region}),
        "cameras": sorted({record.camera_id for record in records if record.camera_id}),
        "road_types": sorted({record.road_type for record in records if record.road_type}),
        "conditions": sorted({record.condition for record in records if record.condition}),
        "weather": sorted({record.weather for record in records if record.weather}),
        "lighting": sorted({record.lighting for record in records if record.lighting}),
        "unresolved_provenance_count": len(acquisition_audit.unresolved_provenance),
        "unresolved_provenance": [dict(item) for item in acquisition_audit.unresolved_provenance],
        "duplicate_hash_groups": [list(group) for group in acquisition_audit.duplicate_hash_groups],
    }

    result = FreezeResult(
        status=status,
        errors=tuple(errors),
        warnings=tuple(warnings),
        dataset_root=str(root),
        dataset_version=dataset_version,
        annotation_version=annotation_version,
        written=False,
        outputs={},
        acquisition=acquisition_summary,
        annotation=annotation_audit.to_dict(),
        leakage=leakage,
        hashes=hashes,
        split_counts=split_counts,
    )
    if status is FreezeStatus.FAIL or not write:
        return result

    # ------------------------------------------------------------- write files
    dataset_yaml = root / "dataset.yaml"
    dataset_yaml.write_text(_dataset_yaml_text(), encoding="utf-8")

    _write_csv(
        root / "manifests" / "collection_sessions.csv",
        COLLECTION_SESSION_COLUMNS,
        _session_rows(records),
    )
    # Recompute after the session CSV is rewritten so the attestation covers the
    # exact bytes that remain on disk.
    hashes = compute_dataset_hashes(root)

    image_entries: List[Dict[str, Any]] = []
    for record in sorted(records, key=lambda item: item.image_id):
        image_entries.append(
            {
                "image_id": record.image_id,
                "file": record.file,
                "split": record.split,
                "session_id": record.capture_session_id,
                "camera_id": record.camera_id,
                "capture_date": record.capture_date,
                "condition": record.condition,
                "road_type": record.road_type,
                "surface_condition": record.surface_condition,
                "weather": record.weather,
                "lighting": record.lighting,
                "route_id": record.route_id,
                "segment_id": record.segment_id,
                "distance_km": record.distance_km,
                "segment_length_m": record.segment_length_m,
                "source_id": record.source_id,
                "licence_id": record.licence_id,
                "original_or_derived": record.original_or_derived,
                "verified_negative": record.image_id in annotation_audit.verified_negative_ids,
                "annotation_final_status": next(
                    (
                        str(row.get("final_status") or "").strip()
                        for row in adjudication_rows
                        if str(row.get("image_id") or "").strip() == record.image_id
                    ),
                    "",
                ),
            }
        )

    manifest = {
        "dataset_version": dataset_version,
        "annotation_version": annotation_version,
        "frozen": status in {FreezeStatus.PASS, FreezeStatus.CONDITIONAL},
        "status": status.value,
        "generated_utc": utc_now(),
        "tool_version": TOOL_VERSION,
        "git_commit": git_commit(Path.cwd()),
        "class_names": {str(key): value for key, value in CLASS_NAMES.items()},
        "label_format": "yolo class cx cy w h (normalized to original image)",
        "provenance": {
            "collection": "independent Phase 43 acquisition",
            "source_ids": acquisition_summary["source_ids"],
            "licences": acquisition_summary["licences"],
            "permission_evidence": acquisition_summary["permission_evidence"],
            "capture_date_range": acquisition_summary["capture_date_range"],
            "countries": acquisition_summary["countries"],
            "regions": acquisition_summary["regions"],
            "cameras": acquisition_summary["cameras"],
            "sessions": acquisition_summary["session_count"],
            "road_types": acquisition_summary["road_types"],
            "conditions": acquisition_summary["conditions"],
            "weather": acquisition_summary["weather"],
            "lighting": acquisition_summary["lighting"],
            "unresolved_provenance_count": acquisition_summary[
                "unresolved_provenance_count"
            ],
        },
        "annotation": {
            "policy": relative_posix(policy, Path.cwd()) if policy.is_absolute() else policy.as_posix(),
            "policy_sha256": policy_sha,
            "version": annotation_version,
            "class_names": {str(key): value for key, value in CLASS_NAMES.items()},
        },
        "quality_control": {
            "annotator_a": list(annotation_audit.annotator_a_ids),
            "annotator_b": list(annotation_audit.annotator_b_ids),
            "adjudication": list(annotation_audit.adjudicator_ids),
            "review_csv": "manifests/annotation_review.csv",
            "adjudication_csv": "manifests/adjudication.csv",
            "reviewer_ids": list(annotation_audit.reviewer_ids),
            "agreement_fraction": annotation_audit.agreement_fraction,
            "verified_negative_count": len(annotation_audit.verified_negative_ids),
            "verified_negative_ids": list(annotation_audit.verified_negative_ids),
            "excluded_ids": list(annotation_audit.excluded_ids),
            "uncertain_ids": list(annotation_audit.uncertain_ids),
        },
        "splits": {
            split: {
                "image_count": split_counts[split],
                "dataset_sha256": hashes["per_split"][split]["dataset_sha256"],
            }
            for split in SPLITS
        },
        "images": image_entries,
        "excluded_images": list(annotation_audit.excluded_ids),
        "uncertain_images": list(annotation_audit.uncertain_ids),
        "leakage": leakage,
        "integrity": {
            "dataset_hashes_file": "manifests/dataset_hashes.json",
            "combined_sha256": hashes["combined_sha256"],
            "test_split_sha256": hashes["per_split"]["test"]["dataset_sha256"],
            "note": (
                "Content hashes detect silent changes; they are not a "
                "cryptographic signature."
            ),
        },
        "frozen_by": frozen_by,
        "limitations": list(warnings),
    }
    manifest_path = root / "manifests" / "independent_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    hashes_payload = {
        "dataset_version": dataset_version,
        "annotation_version": annotation_version,
        "frozen": status in {FreezeStatus.PASS, FreezeStatus.CONDITIONAL},
        "status": status.value,
        "generated_utc": utc_now(),
        "tool_version": TOOL_VERSION,
        "frozen_by": frozen_by,
        "git_commit": git_commit(Path.cwd()),
        "algorithm": "sha256",
        "combined_sha256": hashes["combined_sha256"],
        "image_sha256": hashes["image_sha256"],
        "label_sha256": hashes["label_sha256"],
        "per_split": hashes["per_split"],
        "files": hashes["files"],
        "policy_sha256": policy_sha,
        "integrity_note": (
            "This is a content-hash attestation, not a digital signature. Verify "
            "with scripts/phase43/preflight_dataset.py."
        ),
    }
    hashes_path = root / "manifests" / "dataset_hashes.json"
    hashes_path.write_text(json.dumps(hashes_payload, indent=2), encoding="utf-8")

    readme_path = root / "README.md"
    limitation_lines = "\n".join(f"- {item}" for item in warnings) or "- None recorded."
    readme_path.write_text(
        "\n".join(
            [
                f"# Independent evaluation dataset ({dataset_version})",
                "",
                f"- **Status:** `{status.value}`",
                f"- **Annotation version:** `{annotation_version}`",
                f"- **Frozen by:** {frozen_by}",
                f"- **Classes:** `0 = pothole`, `1 = crack`",
                f"- **Images:** train={split_counts['train']}, "
                f"val={split_counts['val']}, test={split_counts['test']}",
                "",
                "## Contents",
                "",
                "- `images/{train,val,test}/` and `labels/{train,val,test}/`",
                "- `manifests/acquisition_manifest.csv` — per-image provenance",
                "- `manifests/collection_sessions.csv` — session summary",
                "- `manifests/annotation_review.csv` — A/B reviews",
                "- `manifests/adjudication.csv` — adjudication decisions",
                "- `manifests/independent_manifest.json` — Phase 42 manifest",
                "- `manifests/dataset_hashes.json` — content-hash attestation",
                "",
                "## Test split is locked",
                "",
                "`images/test/` must never be used for training, threshold tuning, "
                "model selection or prompt changes.",
                "",
                "## Integrity",
                "",
                f"Combined SHA-256: `{hashes['combined_sha256']}`",
                "",
                f"Test-split SHA-256: `{hashes['per_split']['test']['dataset_sha256']}`",
                "",
                "Hashes detect silent changes. They are **not** a cryptographic "
                "signature and do not prove who froze the dataset.",
                "",
                "## Limitations",
                "",
                limitation_lines,
                "",
                "## Verify",
                "",
                "```",
                "python scripts/phase43/preflight_dataset.py "
                f"--dataset-root {root.as_posix()}",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    outputs = {
        "dataset_yaml": str(dataset_yaml),
        "independent_manifest": str(manifest_path),
        "dataset_hashes": str(hashes_path),
        "collection_sessions": str(root / "manifests" / "collection_sessions.csv"),
        "readme": str(readme_path),
    }
    return FreezeResult(
        status=status,
        errors=tuple(errors),
        warnings=tuple(warnings),
        dataset_root=str(root),
        dataset_version=dataset_version,
        annotation_version=annotation_version,
        written=True,
        outputs=outputs,
        acquisition=acquisition_summary,
        annotation=annotation_audit.to_dict(),
        leakage=leakage,
        hashes=hashes,
        split_counts=split_counts,
    )


def verify_frozen_hashes(root: Path) -> Dict[str, Any]:
    """Recompute hashes and compare them with the frozen attestation."""
    root = Path(root).resolve()
    hashes_path = root / "manifests" / "dataset_hashes.json"
    if not hashes_path.is_file():
        return {
            "ok": False,
            "reason": f"dataset_hashes.json not found at {hashes_path}",
            "mismatches": [],
        }
    try:
        recorded = json.loads(hashes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "reason": f"unreadable dataset_hashes.json: {exc}", "mismatches": []}

    recomputed = compute_dataset_hashes(root)
    mismatches: List[Dict[str, Any]] = []
    for key in ("combined_sha256", "image_sha256", "label_sha256"):
        if recorded.get(key) != recomputed.get(key):
            mismatches.append(
                {"field": key, "recorded": recorded.get(key), "recomputed": recomputed.get(key)}
            )
    recorded_splits = recorded.get("per_split") or {}
    for split in SPLITS:
        recorded_split = (recorded_splits.get(split) or {}).get("dataset_sha256")
        recomputed_split = (recomputed.get("per_split") or {}).get(split, {}).get(
            "dataset_sha256"
        )
        if recorded_split != recomputed_split:
            mismatches.append(
                {
                    "field": f"per_split.{split}.dataset_sha256",
                    "recorded": recorded_split,
                    "recomputed": recomputed_split,
                }
            )
    recorded_files = {item["path"]: item for item in recorded.get("files") or []}
    recomputed_files = {item["path"]: item for item in recomputed.get("files") or []}
    for path, item in sorted(recorded_files.items()):
        current = recomputed_files.get(path)
        if current is None:
            mismatches.append({"field": f"files.{path}", "recorded": item, "recomputed": None})
        elif current["sha256"] != item.get("sha256"):
            mismatches.append(
                {
                    "field": f"files.{path}.sha256",
                    "recorded": item.get("sha256"),
                    "recomputed": current["sha256"],
                }
            )
    for path in sorted(set(recomputed_files) - set(recorded_files)):
        mismatches.append({"field": f"files.{path}", "recorded": None, "recomputed": recomputed_files[path]})

    return {
        "ok": not mismatches,
        "recorded_combined_sha256": recorded.get("combined_sha256"),
        "recomputed_combined_sha256": recomputed.get("combined_sha256"),
        "mismatches": mismatches,
        "checked_file_count": len(recorded_files),
    }


__all__ = [
    "FreezeError",
    "FreezeResult",
    "compute_dataset_hashes",
    "freeze_dataset",
    "verify_frozen_hashes",
]
