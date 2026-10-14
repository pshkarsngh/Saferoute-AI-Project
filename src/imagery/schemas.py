"""SafeRoute AI — Permitted Imagery Domain Contracts & Schemas.

Phase ID: PHASE_14
Follows TRD §10, ARCHITECTURE §8, master_rules.md Rules 1, 8, 9.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ImageryStatus(str, Enum):
    """Categorical outcome of imagery acquisition."""
    AVAILABLE = "available"
    STALE = "stale"
    MISSING = "missing"
    INACCESSIBLE = "inaccessible"
    DISALLOWED_SOURCE = "disallowed_source"
    UNMATCHED = "unmatched"


@dataclass(frozen=True)
class ImageRef:
    """Standardized metadata reference for an acquired road image (TRD §10.1).
    
    Fields:
        image_id: Unique identifier of the image frame.
        file_path: Workspace-local storage path.
        source: Permitted source name (e.g. 'workspace_dashcam_v1', 'mapillary').
        licence: Documented open licence (e.g. 'CC-BY 4.0', 'CC-BY-SA 4.0').
        captured_at: ISO-8601 capture timestamp (if recorded).
        retrieved_at: ISO-8601 acquisition timestamp.
        coordinates: Optional geographic coordinate (lon, lat) where captured.
        distance_to_segment_m: Spatial offset from the road segment line.
        is_stale: Boolean flag indicating if image exceeds staleness threshold.
        status: Categorical status string.
    """
    image_id: str
    file_path: str
    source: str
    licence: str
    retrieved_at: str
    captured_at: Optional[str] = None
    coordinates: Optional[Tuple[float, float]] = None
    distance_to_segment_m: Optional[float] = None
    is_stale: bool = False
    status: str = "available"
    # PHASE_23B: explicit marker so demo/sample imagery can never masquerade as
    # geographically matched route evidence (Rule 9, Rule 20).
    is_demo: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "file_path": self.file_path,
            "source": self.source,
            "licence": self.licence,
            "captured_at": self.captured_at,
            "retrieved_at": self.retrieved_at,
            "coordinates": [round(c, 6) for c in self.coordinates] if self.coordinates else None,
            "distance_to_segment_m": round(float(self.distance_to_segment_m), 1) if self.distance_to_segment_m is not None else None,
            "is_stale": self.is_stale,
            "status": self.status,
            "is_demo": self.is_demo,
        }


@dataclass
class ImageryUnavailable:
    """Explicit descriptor returned when imagery cannot be provided (Rule 9).
    
    Hard Invariant: Unavailable imagery is NEVER safe road proof.
    """
    segment_id: str
    reason: ImageryStatus
    message: str
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "reason": self.reason.value,
            "message": self.message,
            "limitations": list(self.limitations),
        }


@dataclass
class ImageryResult:
    """Standardized response contract for segment imagery retrieval."""
    segment_id: str
    status: ImageryStatus
    images: List[ImageRef] = field(default_factory=list)
    unavailable_detail: Optional[ImageryUnavailable] = None
    source: Optional[str] = None
    licence: Optional[str] = None
    limitations: List[str] = field(default_factory=list)

    @property
    def is_available(self) -> bool:
        return self.status in [ImageryStatus.AVAILABLE, ImageryStatus.STALE] and len(self.images) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "status": self.status.value,
            "is_available": self.is_available,
            "images_count": len(self.images),
            "images": [img.to_dict() for img in self.images],
            "unavailable_detail": self.unavailable_detail.to_dict() if self.unavailable_detail else None,
            "source": self.source,
            "licence": self.licence,
            "limitations": list(self.limitations),
        }
