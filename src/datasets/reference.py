"""P2 — reference-session registry for existing training/validation imagery.

The only locally available session signal is the filename-derived ``capture_date``
in ``data/splits_v2/split_manifest.csv``. That is a **proxy**, not a verified
collection session, and this module says so in every row it emits. A proxy-only
registry can never make the Phase 42 independence gate PASS.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .common import (
    REFERENCE_REGISTRY_COLUMNS,
    relative_posix,
    sha256_file,
    utc_now,
)

PROXY_QUALITY = "filename_date_proxy"
VERIFIED_QUALITY = "verified_collection_session"


class ReferenceRegistryError(ValueError):
    """Raised when the reference registry cannot be built or read."""


@dataclass(frozen=True)
class ReferenceRegistry:
    rows: Tuple[Mapping[str, Any], ...]
    errors: Tuple[str, ...]
    warnings: Tuple[str, ...]
    image_count: int
    session_count: int
    verified: bool
    quality: str
    source_manifest: str
    source_manifest_sha256: Optional[str]

    @property
    def proxy_only(self) -> bool:
        return not self.verified

    def session_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(str(row["session_id"]) for row in self.rows))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rows": [dict(row) for row in self.rows],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "image_count": self.image_count,
            "session_count": self.session_count,
            "verified": self.verified,
            "proxy_only": self.proxy_only,
            "quality": self.quality,
            "source_manifest": self.source_manifest,
            "source_manifest_sha256": self.source_manifest_sha256,
            "note": (
                "Proxy rows group existing images by filename-derived capture date. "
                "They do not prove camera/video/route separation and must not be "
                "presented as verified collection sessions."
            ),
        }


def build_reference_registry(
    split_manifest_csv: Path,
    *,
    image_root: Optional[Path] = None,
) -> ReferenceRegistry:
    """Build a proxy reference registry from the existing split manifest."""
    path = Path(split_manifest_csv)
    if not path.is_file():
        raise ReferenceRegistryError(f"Split manifest not found: {path}")
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ReferenceRegistryError(f"Split manifest is empty: {path}")
    fieldnames = set(rows[0].keys())
    for required in ("capture_date", "split", "stem"):
        if required not in fieldnames:
            raise ReferenceRegistryError(
                f"{path} is missing required column {required!r}; found "
                f"{sorted(fieldnames)}"
            )

    grouped: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []
    errors: List[str] = []
    ignored_duplicates = 0
    for row in rows:
        kept = str(row.get("kept") or "").strip().lower()
        if kept in {"false", "0", "no"}:
            ignored_duplicates += 1
            continue
        split = str(row.get("split") or "unknown").strip().lower()
        capture_date = str(row.get("capture_date") or "").strip()
        if not capture_date:
            capture_date = "unknown-date"
        session_id = f"dateproxy-{capture_date}"
        entry = grouped.setdefault(
            session_id,
            {
                "session_id": session_id,
                "session_id_quality": PROXY_QUALITY,
                "verified": "false",
                "splits": set(),
                "image_count": 0,
                "capture_date": capture_date,
                "camera_ids": set(),
                "route_ids": set(),
                "evidence": (
                    "data/splits_v2/split_manifest.csv filename-derived capture_date"
                ),
            },
        )
        entry["splits"].add(split)
        entry["image_count"] += 1
        camera = str(row.get("camera_id") or "").strip()
        route = str(row.get("route_id") or "").strip()
        if camera:
            entry["camera_ids"].add(camera)
        if route:
            entry["route_ids"].add(route)

    output_rows: List[Dict[str, Any]] = []
    for session_id, entry in sorted(grouped.items()):
        splits = sorted(entry["splits"])
        if len(splits) > 1:
            errors.append(
                f"proxy session {session_id!r} spans multiple splits: {splits}"
            )
        output_rows.append(
            {
                "session_id": session_id,
                "session_id_quality": PROXY_QUALITY,
                "verified": "false",
                "split": splits[0] if len(splits) == 1 else "|".join(splits),
                "image_count": entry["image_count"],
                "capture_date": entry["capture_date"],
                "camera_ids": ";".join(sorted(entry["camera_ids"])),
                "route_ids": ";".join(sorted(entry["route_ids"])),
                "evidence": entry["evidence"],
            }
        )

    if ignored_duplicates:
        warnings.append(
            f"{ignored_duplicates} duplicate-source row(s) were excluded from the "
            "registry because kept=false."
        )
    if not any(row["camera_ids"] for row in output_rows):
        warnings.append(
            "No camera ids exist in the split manifest; camera/video separation "
            "cannot be established from this registry."
        )
    if not any(row["route_ids"] for row in output_rows):
        warnings.append(
            "No route ids exist in the split manifest; route-level separation "
            "cannot be established from this registry."
        )
    warnings.append(
        "The registry is proxy-only. Capture dates come from filenames and do not "
        "prove that no training clip, camera or route supplied independent imagery."
    )

    image_count = sum(int(row["image_count"]) for row in output_rows)
    source_sha = sha256_file(path)
    if image_root is not None:
        root = Path(image_root)
        if not root.is_dir():
            warnings.append(f"image_root does not exist: {root}")
        else:
            present = sum(
                1
                for entry in root.rglob("*")
                if entry.is_file() and entry.suffix.lower() in {".jpg", ".jpeg", ".png"}
            )
            if present != image_count:
                warnings.append(
                    f"image_root contains {present} image(s) but the registry lists "
                    f"{image_count}; the manifest and image directory disagree."
                )

    return ReferenceRegistry(
        rows=tuple(output_rows),
        errors=tuple(errors),
        warnings=tuple(warnings),
        image_count=image_count,
        session_count=len(output_rows),
        verified=False,
        quality=PROXY_QUALITY,
        source_manifest=relative_posix(path, Path.cwd()) if path.is_absolute() else path.as_posix(),
        source_manifest_sha256=source_sha,
    )


def write_reference_registry(
    registry: ReferenceRegistry,
    csv_path: Path,
    *,
    json_report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REFERENCE_REGISTRY_COLUMNS))
        writer.writeheader()
        for row in registry.rows:
            writer.writerow({column: row.get(column, "") for column in REFERENCE_REGISTRY_COLUMNS})
    report = {
        "tool_version": "phase43-v1",
        "generated_utc": utc_now(),
        "registry_csv": str(csv_path),
        "registry": registry.to_dict(),
        "status": "NOT_ASSESSED" if registry.proxy_only else ("FAIL" if registry.errors else "PASS"),
    }
    if json_report_path is not None:
        import json

        Path(json_report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_report_path).write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    return report


def load_reference_registry(path: Path) -> ReferenceRegistry:
    """Load a reference registry (proxy or operator-verified)."""
    path = Path(path)
    if not path.is_file():
        raise ReferenceRegistryError(f"Reference registry not found: {path}")
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        if "session_id" not in fieldnames:
            raise ReferenceRegistryError(
                f"{path} has no 'session_id' column (found {fieldnames})"
            )
        rows = [dict(row) for row in reader]
    if not rows:
        raise ReferenceRegistryError(f"Reference registry is empty: {path}")

    verified_flags = {
        str(row.get("verified") or "").strip().lower() in {"true", "1", "yes"}
        for row in rows
    }
    qualities = {
        str(row.get("session_id_quality") or "").strip() or PROXY_QUALITY
        for row in rows
    }
    verified = verified_flags == {True} and qualities == {VERIFIED_QUALITY}
    errors: List[str] = []
    session_ids = [str(row.get("session_id") or "").strip() for row in rows]
    if any(not session_id for session_id in session_ids):
        errors.append("reference registry contains a blank session_id")
    if len(session_ids) != len(set(session_ids)):
        errors.append("reference registry contains duplicate session_id values")
    warnings: List[str] = []
    if not verified:
        warnings.append(
            "Reference registry is not fully verified; it cannot prove independence."
        )
    image_count = 0
    for row in rows:
        try:
            image_count += int(str(row.get("image_count") or "0") or "0")
        except ValueError:
            pass
    return ReferenceRegistry(
        rows=tuple(rows),
        errors=tuple(errors),
        warnings=tuple(warnings),
        image_count=image_count,
        session_count=len(rows),
        verified=verified,
        quality=next(iter(qualities)) if len(qualities) == 1 else "mixed",
        source_manifest=str(path),
        source_manifest_sha256=sha256_file(path),
    )


__all__ = [
    "PROXY_QUALITY",
    "ReferenceRegistry",
    "ReferenceRegistryError",
    "VERIFIED_QUALITY",
    "build_reference_registry",
    "load_reference_registry",
    "write_reference_registry",
]
