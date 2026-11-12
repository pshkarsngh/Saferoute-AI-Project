"""Shared constants and helpers for Phase 43 dataset governance."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

import yaml

TOOL_VERSION = "phase43-v1"
DATASET_VERSION = "independent-v1"
DEFAULT_ANNOTATION_VERSION = "annotation-v1"
CLASS_NAMES: Mapping[int, str] = {0: "pothole", 1: "crack"}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
SPLITS: Tuple[str, ...] = ("train", "val", "test")
ALLOWED_ORIGINALITY = {"original", "derived"}
ALLOWED_PERMISSION_STATUS = {"approved"}
KNOWN_PERMISSION_STATUSES = {
    "approved",
    "pending",
    "pending_verification",
    "pending_operator_approval",
    "rejected",
    "not_applicable",
}
REVIEW_ROLES = {"annotator_a", "annotator_b"}
REVIEW_STATUSES = {"approved", "changes_requested", "excluded", "uncertain"}
ADJUDICATION_OUTCOMES = {
    "agree",
    "corrected_a",
    "corrected_b",
    "new_annotation",
    "excluded_uncertain",
    "verified_negative",
}
FINAL_STATUSES = {"accepted", "excluded", "uncertain"}

ACQUISITION_COLUMNS: Tuple[str, ...] = (
    "image_id",
    "file",
    "source_id",
    "split",
    "licence_id",
    "licence_evidence",
    "permission_status",
    "original_or_derived",
    "derived_from",
    "capture_session_id",
    "camera_id",
    "capture_date",
    "latitude",
    "longitude",
    "location_accuracy_m",
    "country",
    "region",
    "road_type",
    "surface_condition",
    "weather",
    "lighting",
    "condition",
    "route_id",
    "segment_id",
    "segment_length_m",
    "distance_km",
    "notes",
)
ACQUISITION_REQUIRED_COLUMNS: Tuple[str, ...] = (
    "image_id",
    "file",
    "source_id",
    "split",
    "licence_id",
    "licence_evidence",
    "permission_status",
    "original_or_derived",
    "capture_session_id",
    "camera_id",
    "capture_date",
    "condition",
    "road_type",
    "surface_condition",
    "weather",
    "lighting",
)
COLLECTION_SESSION_COLUMNS: Tuple[str, ...] = (
    "session_id",
    "source_id",
    "camera_id",
    "capture_date",
    "country",
    "region",
    "route_id",
    "image_count",
    "split",
)

REVIEW_COLUMNS: Tuple[str, ...] = (
    "image_id",
    "reviewer_id",
    "role",
    "annotation_version",
    "review_status",
    "box_count",
    "reviewed_at",
    "note",
)
ADJUDICATION_COLUMNS: Tuple[str, ...] = (
    "image_id",
    "adjudicator_id",
    "annotation_version",
    "outcome",
    "final_status",
    "resolved_box_count",
    "decided_at",
    "note",
)
REFERENCE_REGISTRY_COLUMNS: Tuple[str, ...] = (
    "session_id",
    "session_id_quality",
    "verified",
    "split",
    "image_count",
    "capture_date",
    "camera_ids",
    "route_ids",
    "evidence",
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FreezeStatus(str, Enum):
    """Dataset-level status. Missing evidence is NOT_ASSESSED, never PASS."""

    PASS = "PASS"
    CONDITIONAL = "CONDITIONAL"
    FAIL = "FAIL"
    NOT_ASSESSED = "NOT_ASSESSED"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def is_iso_date(value: str) -> bool:
    if not _ISO_DATE.match(value or ""):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def load_yaml(path: Path) -> Mapping[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, Mapping):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def read_json(path: Path) -> Mapping[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")


def resolve_within(root: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``root`` and reject path traversal."""
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes dataset root: {relative!r}") from exc
    return candidate


def relative_posix(path: Path, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def iter_images(directory: Path) -> Iterator[Path]:
    if not directory.is_dir():
        return
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def list_images(directory: Path) -> List[Path]:
    return list(iter_images(directory))


def split_dirs(root: Path) -> Dict[str, Tuple[Path, Path]]:
    return {
        split: (Path(root) / "images" / split, Path(root) / "labels" / split)
        for split in SPLITS
    }


def git_commit(workspace: Path) -> Optional[str]:
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None if completed.returncode == 0 else None


__all__ = [
    "ACQUISITION_COLUMNS",
    "ACQUISITION_REQUIRED_COLUMNS",
    "ADJUDICATION_COLUMNS",
    "ADJUDICATION_OUTCOMES",
    "ALLOWED_ORIGINALITY",
    "ALLOWED_PERMISSION_STATUS",
    "CLASS_NAMES",
    "COLLECTION_SESSION_COLUMNS",
    "DATASET_VERSION",
    "FINAL_STATUSES",
    "FreezeStatus",
    "IMAGE_EXTENSIONS",
    "KNOWN_PERMISSION_STATUSES",
    "REFERENCE_REGISTRY_COLUMNS",
    "REVIEW_COLUMNS",
    "REVIEW_ROLES",
    "REVIEW_STATUSES",
    "SPLITS",
    "TOOL_VERSION",
    "git_commit",
    "is_iso_date",
    "iter_images",
    "list_images",
    "load_yaml",
    "read_json",
    "relative_posix",
    "resolve_within",
    "sha256_file",
    "sha256_text",
    "split_dirs",
    "utc_now",
    "write_json",
]
