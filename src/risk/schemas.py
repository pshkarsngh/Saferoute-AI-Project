"""SafeRoute AI — Hazard Aggregation & Assessment Data Contracts.

Phase ID: PHASE_11
Follows TRD §8.1, ARCHITECTURE §7, master_rules.md Rules 5, 7, 9, 11, 12.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AssessmentStatus(str, Enum):
    """Categorical assessment status for route segments and hazards (Rule 9)."""
    ASSESSED = "assessed"
    PARTIALLY_ASSESSED = "partially_assessed"
    UNASSESSED = "unassessed"
    FAILED = "failed"


@dataclass(frozen=True)
class HazardRecord:
    """Standardized hazard record matching TRD §8.1.
    
    Fields:
        model_version: Model identifier that produced the underlying detection.
        image_id: Source image ID.
        route_id: Associated route ID.
        segment_id: Associated route segment ID.
        hazard_class: Categorical hazard ('pothole', 'crack', 'unsupported_class').
        confidence: Detection confidence [0.0, 1.0].
        bbox_xyxy: Unnormalized pixel coordinates [x1, y1, x2, y2].
        bbox_norm: Normalized coordinates [nx1, ny1, nx2, ny2] within [0.0, 1.0].
        severity: Deterministic severity value computed from policy [1.0, 5.0].
        status: Assessment status ('assessed', 'unsupported_class').
        error: Optional error string.
    """
    model_version: str
    image_id: Optional[str] = None
    route_id: Optional[str] = None
    segment_id: Optional[str] = None
    hazard_class: str = "unsupported_class"
    confidence: float = 0.0
    bbox_xyxy: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    bbox_norm: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    severity: float = 1.0
    status: str = "assessed"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to clean JSON-serializable dictionary matching TRD §8.1."""
        return {
            "model_version": self.model_version,
            "image_id": self.image_id,
            "route_id": self.route_id,
            "segment_id": self.segment_id,
            "hazard_class": self.hazard_class,
            "confidence": round(float(self.confidence), 4),
            "bbox_xyxy": [round(float(c), 2) for c in self.bbox_xyxy],
            "bbox_norm": [round(float(c), 4) for c in self.bbox_norm],
            "severity": round(float(self.severity), 2),
            "status": self.status,
            "error": self.error,
        }


@dataclass
class CoverageInfo:
    """Road imagery coverage metadata for a route segment."""
    images_total: int
    images_used: int
    fraction: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "images_total": self.images_total,
            "images_used": self.images_used,
            "fraction": round(float(self.fraction), 4),
        }


@dataclass
class SegmentAssessment:
    """Segment-level aggregated hazard assessment matching ARCHITECTURE §7.
    
    Hard invariant: Does NOT compute a safety score (Rule 7, Rule 12).
    Safety score calculation is exclusively deferred to the deterministic
    risk engine in Phase 12.
    """
    segment_id: str
    model_version: str
    coverage: CoverageInfo
    hazards: List[HazardRecord] = field(default_factory=list)
    aggregate_hazard: float = 0.0
    status: AssessmentStatus = AssessmentStatus.ASSESSED
    limitations: List[str] = field(default_factory=list)
    route_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "route_id": self.route_id,
            "model_version": self.model_version,
            "coverage": self.coverage.to_dict(),
            "hazards_count": len(self.hazards),
            "hazards": [h.to_dict() for h in self.hazards],
            "aggregate_hazard": round(float(self.aggregate_hazard), 2),
            "status": self.status.value,
            "limitations": list(self.limitations),
        }


@dataclass
class SegmentScoreResult:
    """Segment safety score computed by deterministic risk engine (TRD §9.1, ARCHITECTURE §7)."""
    segment_id: str
    model_version: str
    length_m: float
    coverage: CoverageInfo
    hazard_density_H: Optional[float] = None
    segment_score: Optional[float] = None
    status: AssessmentStatus = AssessmentStatus.ASSESSED
    is_suppressed: bool = False
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "model_version": self.model_version,
            "length_m": round(float(self.length_m), 1),
            "coverage": self.coverage.to_dict(),
            "hazard_density_H": round(float(self.hazard_density_H), 4) if self.hazard_density_H is not None else None,
            "segment_score": round(float(self.segment_score), 2) if self.segment_score is not None else None,
            "status": self.status.value,
            "is_suppressed": self.is_suppressed,
            "limitations": list(self.limitations),
        }


@dataclass
class RouteSafetyResult:
    """Route safety score result strictly matching ARCHITECTURE §7.
    
    Fields:
        route_id: Route identifier.
        model_version: Underlying detector model version.
        route_score: Deterministic score [0.0, 100.0] or None if unassessed.
        coverage: Aggregated route coverage info.
        config_hash: SHA-256 hash of scoring config (Rule 17).
        status: Assessment status.
        segment_scores: List of individual segment score objects.
        limitations: Disclosed limitations (Rule 9, Rule 20).
    """
    route_id: str
    model_version: str
    route_score: Optional[float]
    coverage: CoverageInfo
    config_hash: str
    status: AssessmentStatus = AssessmentStatus.ASSESSED
    segment_scores: List[SegmentScoreResult] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    hazards_total: int = 0
    # PHASE_22: categorical outcome so "no detections" is never read as "safe".
    # hazards_detected | no_hazards_detected | insufficient_coverage |
    # detector_failed | unassessed
    detection_outcome: str = "unassessed"
    safety_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "model_version": self.model_version,
            "route_score": round(float(self.route_score), 2) if self.route_score is not None else None,
            "coverage": self.coverage.to_dict(),
            "config_hash": self.config_hash,
            "status": self.status.value,
            "segments_count": len(self.segment_scores),
            "segment_scores": [s.to_dict() for s in self.segment_scores],
            "limitations": list(self.limitations),
            "hazards_total": int(self.hazards_total),
            "detection_outcome": self.detection_outcome,
            "safety_note": self.safety_note,
        }

