"""SafeRoute AI — Detection Pipeline Data Contracts and Schemas.

Phase ID: PHASE_10
Model Identifier: saferoute-yolo11-v1
Follows: TRD §7.3, ARCHITECTURE §4, master_rules.md Rules 1, 5, 7, 9, 12, 14.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DetectionStatus(str, Enum):
    """Execution status for detection outcomes."""
    SUCCESS = "success"
    NO_DETECTIONS = "no_detections"
    INVALID_IMAGE = "invalid_image"
    MISSING_CHECKPOINT = "missing_checkpoint"
    FAILED = "failed"


@dataclass(frozen=True)
class DetectionRecord:
    """Individual object detection record matching TRD §7.3 & ARCHITECTURE §4.
    
    Fields:
        model_version: Checkpoint model identifier (e.g. 'saferoute-yolo11-v1').
        image_id: Identifier of the source image.
        route_id: Optional route identifier (for route comparisons).
        segment_id: Optional segment identifier along a route.
        hazard_class: Detected class ('pothole', 'crack', or 'unsupported_class').
        confidence: Detector confidence score [0.0, 1.0].
        bbox_xyxy: Unnormalized bounding box [x1, y1, x2, y2] in source image pixels.
        bbox_norm: Normalized bounding box [nx1, ny1, nx2, ny2] within [0.0, 1.0].
        status: Detection record status string ('detected', 'unsupported_class').
        error: Optional error description if detection failed or was anomalous.
    """
    model_version: str
    image_id: Optional[str] = None
    route_id: Optional[str] = None
    segment_id: Optional[str] = None
    hazard_class: str = "unsupported_class"
    confidence: float = 0.0
    bbox_xyxy: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    bbox_norm: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    status: str = "detected"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a clean JSON-serializable dictionary."""
        return {
            "model_version": self.model_version,
            "image_id": self.image_id,
            "route_id": self.route_id,
            "segment_id": self.segment_id,
            "hazard_class": self.hazard_class,
            "confidence": round(float(self.confidence), 4),
            "bbox_xyxy": [round(float(coord), 2) for coord in self.bbox_xyxy],
            "bbox_norm": [round(float(coord), 4) for coord in self.bbox_norm],
            "status": self.status,
            "error": self.error,
        }


@dataclass
class ImageDetectionResult:
    """Complete structured detection response for a single image input.
    
    Inference must NEVER compute safety scores (Rule 7, Rule 12).
    A 'no_detections' status indicates no hazards were identified by the detector;
    it is strictly distinct from proof of a safe road (Rule 9).
    """
    model_version: str
    pipeline_version: str
    status: DetectionStatus
    image_id: Optional[str] = None
    route_id: Optional[str] = None
    segment_id: Optional[str] = None
    detections: List[DetectionRecord] = field(default_factory=list)
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    error: Optional[str] = None
    timing_ms: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a clean JSON-serializable dictionary."""
        return {
            "model_version": self.model_version,
            "pipeline_version": self.pipeline_version,
            "status": self.status.value,
            "image_id": self.image_id,
            "route_id": self.route_id,
            "segment_id": self.segment_id,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "detections_count": len(self.detections),
            "detections": [d.to_dict() for d in self.detections],
            "error": self.error,
            "timing_ms": {k: round(v, 2) for k, v in self.timing_ms.items()},
        }
