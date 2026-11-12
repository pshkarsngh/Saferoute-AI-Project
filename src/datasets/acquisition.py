"""P2 — provenance schema validation and safe ingestion.

The acquisition manifest is the single source of truth for *why* an image is
allowed to exist in the independent dataset. Ingestion refuses to copy a file
when its source is not explicitly approved, its licence evidence is missing, its
session metadata is absent, or it duplicates the reference corpus.
"""

from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..evaluation.dataset_validation import compute_file_sha256
from ..evaluation.leakage import hamming_distance, perceptual_hash
from .common import (
    ACQUISITION_COLUMNS,
    ACQUISITION_REQUIRED_COLUMNS,
    ALLOWED_ORIGINALITY,
    ALLOWED_PERMISSION_STATUS,
    CLASS_NAMES,
    COLLECTION_SESSION_COLUMNS,
    IMAGE_EXTENSIONS,
    SPLITS,
    is_iso_date,
    list_images,
    relative_posix,
    resolve_within,
    sha256_file,
    split_dirs,
    utc_now,
)
from .sources import SourceRecord

DEFAULT_MAX_HAMMING_DISTANCE = 8
OPTIONAL_PROVENANCE_FIELDS: Tuple[str, ...] = (
    "latitude",
    "longitude",
    "location_accuracy_m",
    "country",
    "region",
    "route_id",
    "segment_id",
    "distance_km",
)


class AcquisitionError(ValueError):
    """Raised when the acquisition manifest is structurally unusable."""


def _optional_float(field_name: str, raw: Any, image_id: str) -> Optional[float]:
    text = str(raw if raw is not None else "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise AcquisitionError(
            f"image {image_id!r}: {field_name} is not numeric: {text!r}"
        ) from exc


@dataclass(frozen=True)
class AcquisitionRecord:
    image_id: str
    file: str
    source_id: str
    split: str
    licence_id: str
    licence_evidence: str
    permission_status: str
    original_or_derived: str
    derived_from: str
    capture_session_id: str
    camera_id: str
    capture_date: str
    condition: str
    road_type: str
    surface_condition: str
    weather: str
    lighting: str
    country: str = ""
    region: str = ""
    route_id: str = ""
    segment_id: str = ""
    notes: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy_m: Optional[float] = None
    segment_length_m: Optional[float] = None
    distance_km: Optional[float] = None
    extra: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> "AcquisitionRecord":
        image_id = str(row.get("image_id") or "").strip()
        if not image_id:
            raise AcquisitionError("acquisition row has no image_id")
        return cls(
            image_id=image_id,
            file=str(row.get("file") or "").strip().replace("\\", "/"),
            source_id=str(row.get("source_id") or "").strip(),
            split=str(row.get("split") or "").strip().lower(),
            licence_id=str(row.get("licence_id") or "").strip(),
            licence_evidence=str(row.get("licence_evidence") or "").strip(),
            permission_status=str(row.get("permission_status") or "").strip(),
            original_or_derived=str(row.get("original_or_derived") or "").strip().lower(),
            derived_from=str(row.get("derived_from") or "").strip(),
            capture_session_id=str(row.get("capture_session_id") or "").strip(),
            camera_id=str(row.get("camera_id") or "").strip(),
            capture_date=str(row.get("capture_date") or "").strip(),
            condition=str(row.get("condition") or "").strip(),
            road_type=str(row.get("road_type") or "").strip(),
            surface_condition=str(row.get("surface_condition") or "").strip(),
            weather=str(row.get("weather") or "").strip(),
            lighting=str(row.get("lighting") or "").strip(),
            country=str(row.get("country") or "").strip(),
            region=str(row.get("region") or "").strip(),
            route_id=str(row.get("route_id") or "").strip(),
            segment_id=str(row.get("segment_id") or "").strip(),
            notes=str(row.get("notes") or "").strip(),
            latitude=_optional_float("latitude", row.get("latitude"), image_id),
            longitude=_optional_float("longitude", row.get("longitude"), image_id),
            location_accuracy_m=_optional_float(
                "location_accuracy_m", row.get("location_accuracy_m"), image_id
            ),
            segment_length_m=_optional_float(
                "segment_length_m", row.get("segment_length_m"), image_id
            ),
            distance_km=_optional_float("distance_km", row.get("distance_km"), image_id),
            extra={
                str(key): str(value)
                for key, value in row.items()
                if key not in ACQUISITION_COLUMNS and value not in (None, "")
            },
        )

    @property
    def session_id(self) -> str:
        return self.capture_session_id

    def as_row(self) -> Dict[str, str]:
        def text(value: Any) -> str:
            return "" if value is None else str(value)

        row = {
            "image_id": self.image_id,
            "file": self.file,
            "source_id": self.source_id,
            "split": self.split,
            "licence_id": self.licence_id,
            "licence_evidence": self.licence_evidence,
            "permission_status": self.permission_status,
            "original_or_derived": self.original_or_derived,
            "derived_from": self.derived_from,
            "capture_session_id": self.capture_session_id,
            "camera_id": self.camera_id,
            "capture_date": self.capture_date,
            "latitude": text(self.latitude),
            "longitude": text(self.longitude),
            "location_accuracy_m": text(self.location_accuracy_m),
            "country": self.country,
            "region": self.region,
            "road_type": self.road_type,
            "surface_condition": self.surface_condition,
            "weather": self.weather,
            "lighting": self.lighting,
            "condition": self.condition,
            "route_id": self.route_id,
            "segment_id": self.segment_id,
            "segment_length_m": text(self.segment_length_m),
            "distance_km": text(self.distance_km),
            "notes": self.notes,
        }
        row.update({key: value for key, value in self.extra.items() if key not in row})
        return row


@dataclass(frozen=True)
class AcquisitionAudit:
    records: Tuple[AcquisitionRecord, ...]
    errors: Tuple[str, ...]
    warnings: Tuple[str, ...]
    unresolved_provenance: Tuple[Mapping[str, Any], ...]
    duplicate_hash_groups: Tuple[Tuple[str, ...], ...]
    reference_exact_matches: Tuple[Mapping[str, Any], ...]
    reference_near_matches: Tuple[Mapping[str, Any], ...]
    split_counts: Mapping[str, int]
    session_count: int

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "record_count": len(self.records),
            "image_count": len(self.records),
            "split_counts": dict(self.split_counts),
            "session_count": self.session_count,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "unresolved_provenance_count": len(self.unresolved_provenance),
            "unresolved_provenance": [dict(item) for item in self.unresolved_provenance],
            "exact_duplicate_group_count": len(self.duplicate_hash_groups),
            "exact_duplicate_groups": [list(group) for group in self.duplicate_hash_groups],
            "reference_exact_match_count": len(self.reference_exact_matches),
            "reference_exact_matches": [dict(item) for item in self.reference_exact_matches],
            "reference_near_match_count": len(self.reference_near_matches),
            "reference_near_matches": [dict(item) for item in self.reference_near_matches],
            "classes": {str(key): value for key, value in CLASS_NAMES.items()},
        }


def load_acquisition_csv(path: Path) -> Tuple[Tuple[AcquisitionRecord, ...], List[str]]:
    path = Path(path)
    if not path.is_file():
        raise AcquisitionError(f"Acquisition manifest not found: {path}")
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        missing = [name for name in ACQUISITION_REQUIRED_COLUMNS if name not in fieldnames]
        if missing:
            raise AcquisitionError(
                f"{path} is missing required columns: {missing}. "
                f"Found: {fieldnames}"
            )
        rows = [dict(row) for row in reader]
    if not rows:
        raise AcquisitionError(f"{path} contains no acquisition rows")
    records: List[AcquisitionRecord] = []
    seen = set()
    for line_number, row in enumerate(rows, start=2):
        record = AcquisitionRecord.from_row(row)
        if record.image_id in seen:
            raise AcquisitionError(
                f"{path}:{line_number}: duplicate image_id {record.image_id!r}"
            )
        seen.add(record.image_id)
        records.append(record)
    return tuple(records), fieldnames


def _overlap_with_reference(
    records: Sequence[AcquisitionRecord],
    paths: Mapping[str, Path],
    reference_image_paths: Sequence[Path],
    max_hamming_distance: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    exact: List[Dict[str, Any]] = []
    near: List[Dict[str, Any]] = []
    references = [Path(path) for path in reference_image_paths if Path(path).is_file()]
    if not references:
        return exact, near
    reference_hash_by_digest: Dict[str, str] = {}
    reference_phashes: List[Tuple[str, int]] = []
    for reference in references:
        reference_hash_by_digest[compute_file_sha256(reference)] = str(reference)
        reference_phashes.append((str(reference), perceptual_hash(reference)))

    for record in records:
        path = paths.get(record.image_id)
        if path is None:
            continue
        digest = compute_file_sha256(path)
        if digest in reference_hash_by_digest:
            exact.append(
                {
                    "image_id": record.image_id,
                    "reference": reference_hash_by_digest[digest],
                }
            )
            continue
        image_phash = perceptual_hash(path)
        for reference_name, reference_phash in reference_phashes:
            distance = hamming_distance(image_phash, reference_phash)
            if distance <= max_hamming_distance:
                near.append(
                    {
                        "image_id": record.image_id,
                        "reference": reference_name,
                        "hamming_distance": distance,
                    }
                )
                break
    return exact, near


def validate_acquisition(
    records: Sequence[AcquisitionRecord],
    *,
    sources: Mapping[str, SourceRecord],
    images_root: Optional[Path] = None,
    require_layout: bool = True,
    check_files: bool = True,
    reference_image_paths: Sequence[Path] = (),
    max_hamming_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
) -> AcquisitionAudit:
    errors: List[str] = []
    warnings: List[str] = []
    unresolved: List[Dict[str, Any]] = []
    paths: Dict[str, Path] = {}
    hashes: Dict[str, List[str]] = {}
    sessions: Dict[str, List[AcquisitionRecord]] = {}
    split_counts = {split: 0 for split in SPLITS}
    root = Path(images_root).resolve() if images_root is not None else None

    if check_files and root is None:
        raise AcquisitionError("images_root is required when check_files is true")

    for record in records:
        prefix = f"image {record.image_id!r}"
        if not record.file:
            errors.append(f"{prefix}: file is empty")
            continue
        if not record.source_id:
            errors.append(f"{prefix}: source_id is empty")
        source = sources.get(record.source_id)
        if source is None:
            errors.append(f"{prefix}: unknown source_id {record.source_id!r}")
        else:
            if not source.approved_for_acquisition:
                errors.append(
                    f"{prefix}: source {source.source_id!r} is not approved for "
                    "acquisition"
                )
            if source.reference_only:
                errors.append(
                    f"{prefix}: source {source.source_id!r} is reference-only and "
                    "cannot supply independent evaluation imagery"
                )
            if (
                source.licence_id
                and record.licence_id
                and source.licence_id != record.licence_id
            ):
                warnings.append(
                    f"{prefix}: licence_id {record.licence_id!r} differs from source "
                    f"registry {source.licence_id!r}"
                )
        if record.permission_status not in ALLOWED_PERMISSION_STATUS:
            errors.append(
                f"{prefix}: permission_status is {record.permission_status!r}; "
                "only 'approved' may be ingested"
            )
        if not record.licence_id:
            errors.append(f"{prefix}: licence_id is empty")
        if not record.licence_evidence:
            errors.append(f"{prefix}: licence_evidence is empty")
        if record.original_or_derived not in ALLOWED_ORIGINALITY:
            errors.append(
                f"{prefix}: original_or_derived must be one of "
                f"{sorted(ALLOWED_ORIGINALITY)}, got {record.original_or_derived!r}"
            )
        elif record.original_or_derived == "derived" and not record.derived_from:
            errors.append(f"{prefix}: derived image has no derived_from")
        if not record.capture_session_id:
            errors.append(f"{prefix}: capture_session_id is empty")
        if not record.camera_id:
            errors.append(f"{prefix}: camera_id is empty")
        if not is_iso_date(record.capture_date):
            errors.append(
                f"{prefix}: capture_date must be YYYY-MM-DD, got "
                f"{record.capture_date!r}"
            )
        for name in ("condition", "road_type", "surface_condition", "weather", "lighting"):
            if not str(getattr(record, name) or "").strip():
                errors.append(f"{prefix}: {name} is empty")
        if record.split not in SPLITS:
            errors.append(f"{prefix}: split must be one of {list(SPLITS)}, got {record.split!r}")
        else:
            split_counts[record.split] += 1
            if require_layout and not record.file.startswith(f"images/{record.split}/"):
                errors.append(
                    f"{prefix}: file {record.file!r} must live under "
                    f"images/{record.split}/"
                )

        if (record.latitude is None) != (record.longitude is None):
            errors.append(f"{prefix}: latitude and longitude must be supplied together")
        if record.latitude is not None and not (-90.0 <= record.latitude <= 90.0):
            errors.append(f"{prefix}: latitude out of range: {record.latitude}")
        if record.longitude is not None and not (-180.0 <= record.longitude <= 180.0):
            errors.append(f"{prefix}: longitude out of range: {record.longitude}")
        if record.location_accuracy_m is not None and record.location_accuracy_m <= 0:
            errors.append(f"{prefix}: location_accuracy_m must be positive")
        if record.distance_km is not None and record.distance_km <= 0:
            errors.append(f"{prefix}: distance_km must be positive")
        if record.segment_length_m is not None and record.segment_length_m <= 0:
            errors.append(f"{prefix}: segment_length_m must be positive")

        missing_optional = []
        for field_name in OPTIONAL_PROVENANCE_FIELDS:
            value = getattr(record, field_name)
            if value in (None, ""):
                missing_optional.append(field_name)
        if missing_optional:
            unresolved.append({"image_id": record.image_id, "missing_fields": missing_optional})

        sessions.setdefault(record.capture_session_id, []).append(record)

        if check_files and root is not None:
            try:
                path = resolve_within(root, record.file)
            except ValueError as exc:
                errors.append(f"{prefix}: {exc}")
                continue
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                errors.append(f"{prefix}: unsupported image suffix {path.suffix!r}")
                continue
            if not path.is_file():
                errors.append(f"{prefix}: file not found: {record.file}")
                continue
            paths[record.image_id] = path
            hashes.setdefault(sha256_file(path), []).append(record.image_id)

    duplicate_groups: List[Tuple[str, ...]] = []
    for digest, image_ids in hashes.items():
        if len(image_ids) > 1:
            duplicate_groups.append(tuple(sorted(image_ids)))
            errors.append(
                "exact duplicate image bytes share one SHA-256: "
                + ", ".join(sorted(image_ids))
            )

    if require_layout and check_files and root is not None:
        documented = {path.resolve() for path in paths.values()}
        for split, (image_dir, _) in split_dirs(root).items():
            for path in list_images(image_dir):
                if path.resolve() not in documented:
                    errors.append(
                        f"undocumented image file under images/{split}/: "
                        f"{relative_posix(path, root)}"
                    )

    for session_id, session_records in sorted(sessions.items()):
        session_splits = sorted({record.split for record in session_records})
        if len(session_splits) > 1:
            errors.append(
                f"session {session_id!r} crosses splits {session_splits}; whole "
                "sessions must stay on one side"
            )
        cameras = {record.camera_id for record in session_records}
        if len(cameras) > 1:
            warnings.append(
                f"session {session_id!r} records multiple camera ids: {sorted(cameras)}"
            )
        dates = {record.capture_date for record in session_records}
        if len(dates) > 1:
            warnings.append(
                f"session {session_id!r} records multiple capture dates: {sorted(dates)}"
            )

    exact_matches, near_matches = _overlap_with_reference(
        records, paths, reference_image_paths, max_hamming_distance
    )
    for match in exact_matches:
        errors.append(
            f"image {match['image_id']!r} is byte-identical to reference image "
            f"{match['reference']}"
        )
    for match in near_matches:
        errors.append(
            f"image {match['image_id']!r} is a perceptual near-duplicate of reference "
            f"image {match['reference']} (hamming={match['hamming_distance']})"
        )

    if not reference_image_paths:
        warnings.append(
            "No reference imagery supplied, so image-level reference overlap was not "
            "checked."
        )

    return AcquisitionAudit(
        records=tuple(records),
        errors=tuple(errors),
        warnings=tuple(warnings),
        unresolved_provenance=tuple(unresolved),
        duplicate_hash_groups=tuple(duplicate_groups),
        reference_exact_matches=tuple(exact_matches),
        reference_near_matches=tuple(near_matches),
        split_counts=split_counts,
        session_count=len(sessions),
    )


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def ingest_acquisition(
    acquisition_csv: Path,
    staging_images: Path,
    output_root: Path,
    *,
    sources: Mapping[str, SourceRecord],
    reference_image_paths: Sequence[Path] = (),
    dry_run: bool = False,
    overwrite: bool = False,
    max_hamming_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
) -> Dict[str, Any]:
    """Validate a staged acquisition and copy it into the independent layout."""
    staging = Path(staging_images)
    output = Path(output_root)
    records, fieldnames = load_acquisition_csv(Path(acquisition_csv))
    audit = validate_acquisition(
        records,
        sources=sources,
        images_root=staging,
        require_layout=False,
        check_files=True,
        reference_image_paths=reference_image_paths,
        max_hamming_distance=max_hamming_distance,
    )
    report: Dict[str, Any] = {
        "tool_version": "phase43-v1",
        "generated_utc": utc_now(),
        "acquisition_csv": str(acquisition_csv),
        "staging_images": str(staging),
        "output_root": str(output),
        "dry_run": dry_run,
        "written": False,
        "status": "FAIL" if audit.errors else ("READY" if dry_run else "INGESTED"),
        "audit": audit.to_dict(),
    }
    if audit.errors:
        return report

    existing = []
    for split in SPLITS:
        existing.extend(list_images(output / "images" / split))
    if existing and not overwrite:
        report["status"] = "FAIL"
        report["audit"]["errors"].append(
            f"output already contains {len(existing)} image(s); pass overwrite=True "
            "only after reviewing the existing dataset"
        )
        return report

    planned: List[Dict[str, str]] = []
    seen_targets = set()
    for record in records:
        source_path = resolve_within(staging, record.file)
        suffix = source_path.suffix.lower()
        target_relative = f"images/{record.split}/{record.image_id}{suffix}"
        if target_relative in seen_targets:
            report["status"] = "FAIL"
            report["audit"]["errors"].append(
                f"duplicate target path would be created: {target_relative}"
            )
            return report
        seen_targets.add(target_relative)
        planned.append(
            {
                "image_id": record.image_id,
                "from": str(source_path),
                "to": target_relative,
                "split": record.split,
            }
        )
    report["planned_copies"] = planned
    if dry_run:
        return report

    for item in planned:
        target = output / item["to"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item["from"], target)

    updated_rows = []
    for record in records:
        row = record.as_row()
        row["file"] = next(
            item["to"] for item in planned if item["image_id"] == record.image_id
        )
        updated_rows.append(row)
    columns = list(fieldnames)
    for name in ACQUISITION_COLUMNS:
        if name not in columns:
            columns.append(name)
    _write_csv(output / "manifests" / "acquisition_manifest.csv", columns, updated_rows)

    session_rows: Dict[str, Dict[str, Any]] = {}
    for record in records:
        entry = session_rows.setdefault(
            record.capture_session_id,
            {
                "session_id": record.capture_session_id,
                "source_id": record.source_id,
                "camera_id": record.camera_id,
                "capture_date": record.capture_date,
                "country": record.country,
                "region": record.region,
                "route_id": record.route_id,
                "image_count": 0,
                "split": record.split,
            },
        )
        entry["image_count"] += 1
    _write_csv(
        output / "manifests" / "collection_sessions.csv",
        COLLECTION_SESSION_COLUMNS,
        sorted(session_rows.values(), key=lambda row: row["session_id"]),
    )
    report["written"] = True
    report["outputs"] = {
        "images_root": relative_posix(output / "images", output),
        "acquisition_manifest": "manifests/acquisition_manifest.csv",
        "collection_sessions": "manifests/collection_sessions.csv",
    }
    return report


__all__ = [
    "AcquisitionAudit",
    "AcquisitionError",
    "AcquisitionRecord",
    "DEFAULT_MAX_HAMMING_DISTANCE",
    "ingest_acquisition",
    "load_acquisition_csv",
    "validate_acquisition",
]
