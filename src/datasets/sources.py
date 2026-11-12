"""Approved-source and licence registry for Phase 43.

Acquisition is impossible to approve from code alone. This module reads an
operator-maintained registry and reports exactly which sources are allowed. The
committed registry intentionally approves nothing: every candidate source needs
an explicit human decision (and, where relevant, accepted licence terms).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .common import KNOWN_PERMISSION_STATUSES, load_yaml


class SourceRegistryError(ValueError):
    """Raised when the source registry is structurally invalid."""


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    name: str
    licence_id: str
    licence_url: str
    permission_status: str
    approved_for_acquisition: bool
    reference_only: bool
    evidence: str
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "licence_id": self.licence_id,
            "licence_url": self.licence_url,
            "permission_status": self.permission_status,
            "approved_for_acquisition": self.approved_for_acquisition,
            "reference_only": self.reference_only,
            "evidence": self.evidence,
            "notes": self.notes,
        }


def load_source_registry(path: Path) -> Dict[str, SourceRecord]:
    if not Path(path).is_file():
        raise SourceRegistryError(f"Source registry not found: {path}")
    data = load_yaml(Path(path))
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise SourceRegistryError(f"{path} must contain a non-empty 'sources' list")

    sources: Dict[str, SourceRecord] = {}
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, Mapping):
            raise SourceRegistryError(f"{path}: sources[{index}] must be a mapping")
        source_id = str(raw.get("source_id") or "").strip()
        if not source_id:
            raise SourceRegistryError(f"{path}: sources[{index}] has no source_id")
        if source_id in sources:
            raise SourceRegistryError(f"{path}: duplicate source_id {source_id!r}")
        permission_status = str(raw.get("permission_status") or "").strip()
        if permission_status not in KNOWN_PERMISSION_STATUSES:
            raise SourceRegistryError(
                f"{path}: source {source_id!r} has unknown permission_status "
                f"{permission_status!r}"
            )
        approved = bool(raw.get("approved_for_acquisition"))
        if approved and permission_status != "approved":
            raise SourceRegistryError(
                f"{path}: source {source_id!r} is approved_for_acquisition but "
                f"permission_status is {permission_status!r}"
            )
        sources[source_id] = SourceRecord(
            source_id=source_id,
            name=str(raw.get("name") or source_id),
            licence_id=str(raw.get("licence_id") or ""),
            licence_url=str(raw.get("licence_url") or ""),
            permission_status=permission_status,
            approved_for_acquisition=approved,
            reference_only=bool(raw.get("reference_only")),
            evidence=str(raw.get("evidence") or ""),
            notes=str(raw.get("notes") or ""),
        )
    return sources


def audit_source_registry(
    sources: Mapping[str, SourceRecord],
    *,
    workspace: Optional[Path] = None,
) -> Dict[str, Any]:
    """Report approval state without granting any approval itself."""
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []
    for source in sorted(sources.values(), key=lambda item: item.source_id):
        evidence_exists: Optional[bool] = None
        if source.evidence and workspace is not None:
            evidence_exists = (Path(workspace) / source.evidence).exists()
            if not evidence_exists:
                warnings.append(
                    f"source {source.source_id!r} evidence file is missing: "
                    f"{source.evidence}"
                )
        if source.approved_for_acquisition:
            if not source.licence_id:
                errors.append(
                    f"source {source.source_id!r} is approved but records no licence_id"
                )
            if not source.licence_url and not source.evidence:
                errors.append(
                    f"source {source.source_id!r} is approved but records neither "
                    "licence_url nor evidence"
                )
        rows.append(
            {
                **source.to_dict(),
                "evidence_exists": evidence_exists,
            }
        )
    approved = [row["source_id"] for row in rows if row["approved_for_acquisition"]]
    return {
        "sources": rows,
        "approved_source_ids": approved,
        "approved_count": len(approved),
        "acquisition_allowed": bool(approved),
        "errors": errors,
        "warnings": warnings,
        "note": (
            "A source is usable only when approved_for_acquisition is true after a "
            "human licence/permission decision. This audit grants no approval."
        ),
    }


__all__ = [
    "SourceRecord",
    "SourceRegistryError",
    "audit_source_registry",
    "load_source_registry",
]
