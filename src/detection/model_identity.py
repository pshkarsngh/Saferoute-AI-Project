"""SafeRoute AI — truthful model checkpoint identity (PHASE_44).

The project must never present a P0 smoke substitute as the genuine
``saferoute-yolo11-v2`` checkpoint.  This module resolves identity from the
artifacts that actually exist on disk without loading YOLO:

* the checkpoint file (presence, size, SHA-256),
* a P0 smoke marker beside the checkpoint,
* an explicit registry of independently verified checkpoint hashes.

Reported statuses
-----------------
``MODEL_UNAVAILABLE``
    No checkpoint file exists at the configured path.
``SMOKE_SUBSTITUTE``
    A non-production P0 smoke marker is present.  Detection may still run for
    pipeline smoke evidence, but it is explicitly **not validated** and must
    never be described as genuine v1/v2 performance.
``UNVERIFIED_MODEL``
    A checkpoint file exists but its hash is not in the verified registry.
``VERIFIED_MODEL``
    The checkpoint hash matches an independently verified entry.  The registry
    is empty today because the genuine v2 artifact has never been recovered.

Nothing here changes detection thresholds, the risk formula or the marker file.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

MODEL_STATUS_UNAVAILABLE = "MODEL_UNAVAILABLE"
MODEL_STATUS_SMOKE_SUBSTITUTE = "SMOKE_SUBSTITUTE"
MODEL_STATUS_UNVERIFIED = "UNVERIFIED_MODEL"
MODEL_STATUS_VERIFIED = "VERIFIED_MODEL"

#: Effective label used for any smoke substitute.  The configured directory may
#: still be named ``saferoute-yolo11-v2``; that declared name is reported
#: separately and is never used as the effective model identity for smoke data.
SMOKE_MODEL_LABEL = "p0-smoke-substitute"

#: Marker filenames that denote a non-production smoke checkpoint.
SMOKE_MARKER_NAMES = ("P0_SMOKE_SUBSTITUTE.json", "P0_SMOKE_MODEL.json")

#: Checkpoint SHA-256 values that have been independently verified.
#:
#: Intentionally empty: the genuine ``saferoute-yolo11-v2`` artifact is absent
#: (Phase 42/43/44 audits).  A documented genuine hash
#: (B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA) has no
#: corresponding file in this workspace, so registering it would imply a
#: verification that cannot be performed.  Add entries only with an approved,
#: reproducible independent evaluation record.
VERIFIED_CHECKPOINT_SHA256: Dict[str, str] = {}

DEFAULT_CHECKPOINT_REL = Path("models/training/saferoute-yolo11-v2/weights/best.pt")


@dataclass(frozen=True)
class ModelIdentity:
    """Machine-readable identity and validation state for a checkpoint."""

    status: str
    declared_model_version: str
    model_version: str
    checkpoint_present: bool
    checkpoint_sha256: Optional[str] = None
    checkpoint_bytes: Optional[int] = None
    checkpoint_path: Optional[str] = None
    marker_present: bool = False
    marker_path: Optional[str] = None
    marker_status: Optional[str] = None
    marker_warning: Optional[str] = None
    validated: bool = False
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe identity record (no secrets, workspace-relative path)."""
        return {
            "status": self.status,
            "declared_model_version": self.declared_model_version,
            "model_version": self.model_version,
            "checkpoint_present": self.checkpoint_present,
            "checkpoint_sha256": self.checkpoint_sha256,
            "checkpoint_bytes": self.checkpoint_bytes,
            "checkpoint_path": self.checkpoint_path,
            "marker_present": self.marker_present,
            "marker_path": self.marker_path,
            "marker_status": self.marker_status,
            "marker_warning": self.marker_warning,
            "validated": self.validated,
            "detail": self.detail,
        }


def _relative_if_inside(path: Path, workspace_root: Optional[Path]) -> str:
    if workspace_root is not None:
        try:
            return path.resolve().relative_to(workspace_root.resolve()).as_posix()
        except ValueError:
            pass
    return path.name


@lru_cache(maxsize=32)
def _sha256_file(path_str: str, size: int, mtime_ns: int) -> str:
    """Hash a checkpoint once per (path, size, mtime) without loading it."""
    digest = hashlib.sha256()
    with open(path_str, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _find_smoke_marker(checkpoint: Path) -> Optional[Path]:
    """Return a smoke marker beside the checkpoint weights, if present."""
    search_dirs = [checkpoint.parent, checkpoint.parent.parent]
    for directory in search_dirs:
        for name in SMOKE_MARKER_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def _read_marker(marker: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return ``(status, warning, note)`` from a marker JSON, tolerating damage."""
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None, None
    if not isinstance(data, dict):
        return None, None, None
    status = data.get("status") if isinstance(data.get("status"), str) else None
    warning = data.get("warning") if isinstance(data.get("warning"), str) else None
    note = data.get("note") if isinstance(data.get("note"), str) else None
    return status, warning, note


def resolve_checkpoint_identity(
    checkpoint_path: Path,
    declared_model_version: Optional[str] = None,
    workspace_root: Optional[Path] = None,
) -> ModelIdentity:
    """Resolve identity for an explicit checkpoint path."""
    checkpoint = Path(checkpoint_path)
    root = Path(workspace_root) if workspace_root is not None else None
    declared = declared_model_version or _declared_version_from_path(checkpoint)

    if not checkpoint.is_file():
        return ModelIdentity(
            status=MODEL_STATUS_UNAVAILABLE,
            declared_model_version=declared,
            model_version=declared,
            checkpoint_present=False,
            checkpoint_path=_relative_if_inside(checkpoint, root),
            validated=False,
            detail=(
                "No checkpoint file exists at the configured path; detection "
                "cannot run and no safety claim may be made."
            ),
        )

    stat = checkpoint.stat()
    sha256 = _sha256_file(str(checkpoint.resolve()), stat.st_size, stat.st_mtime_ns)
    marker = _find_smoke_marker(checkpoint)

    if marker is not None:
        marker_status, marker_warning, marker_note = _read_marker(marker)
        warning = marker_warning or marker_note or (
            "A P0 smoke marker is present beside this checkpoint."
        )
        return ModelIdentity(
            status=MODEL_STATUS_SMOKE_SUBSTITUTE,
            declared_model_version=declared,
            model_version=SMOKE_MODEL_LABEL,
            checkpoint_present=True,
            checkpoint_sha256=sha256,
            checkpoint_bytes=stat.st_size,
            checkpoint_path=_relative_if_inside(checkpoint, root),
            marker_present=True,
            marker_path=_relative_if_inside(marker, root),
            marker_status=marker_status,
            marker_warning=warning,
            validated=False,
            detail=(
                "This checkpoint is a non-production P0 smoke substitute, not a "
                "genuine trained release. Detection output is pipeline-evidence "
                "only; no real-world safety claim or recommendation is issued."
            ),
        )

    verified_for = VERIFIED_CHECKPOINT_SHA256.get(sha256)
    if verified_for is not None:
        return ModelIdentity(
            status=MODEL_STATUS_VERIFIED,
            declared_model_version=declared,
            model_version=declared,
            checkpoint_present=True,
            checkpoint_sha256=sha256,
            checkpoint_bytes=stat.st_size,
            checkpoint_path=_relative_if_inside(checkpoint, root),
            validated=True,
            detail=f"Checkpoint hash matches the independently verified '{verified_for}' entry.",
        )

    return ModelIdentity(
        status=MODEL_STATUS_UNVERIFIED,
        declared_model_version=declared,
        model_version=declared,
        checkpoint_present=True,
        checkpoint_sha256=sha256,
        checkpoint_bytes=stat.st_size,
        checkpoint_path=_relative_if_inside(checkpoint, root),
        validated=False,
        detail=(
            "The checkpoint file exists but its SHA-256 is not in the verified "
            "registry, so its detection quality is unverified and no safety "
            "claim or recommendation is issued."
        ),
    )


def _declared_version_from_path(checkpoint: Path) -> str:
    parts = checkpoint.parts
    if len(parts) >= 3 and parts[-2] == "weights":
        candidate = parts[-3]
        if candidate.startswith("saferoute-yolo11-"):
            return candidate
    return "saferoute-yolo11-v2"


def _configured_checkpoint(workspace_root: Path) -> Tuple[Path, Optional[str]]:
    """Read the serving checkpoint path from detection config without loading YOLO."""
    config_path = workspace_root / "config" / "detection.yaml"
    relative = DEFAULT_CHECKPOINT_REL
    if config_path.is_file():
        try:
            import yaml

            with open(config_path, "r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle) or {}
            configured = (config.get("model") or {}).get("checkpoint")
            if configured:
                relative = Path(str(configured))
        except (OSError, ValueError):
            relative = DEFAULT_CHECKPOINT_REL
    return (workspace_root / relative).resolve(), _declared_version_from_path(relative)


def resolve_configured_identity(workspace_root: Optional[Path] = None) -> ModelIdentity:
    """Resolve identity for the configured serving checkpoint (no YOLO load)."""
    root = Path(workspace_root) if workspace_root is not None else Path(__file__).resolve().parents[2]
    checkpoint, declared = _configured_checkpoint(root)
    return resolve_checkpoint_identity(checkpoint, declared_model_version=declared, workspace_root=root)
