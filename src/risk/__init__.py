"""SafeRoute AI — Risk Engine & Hazard Aggregation Package.

Phase ID: PHASE_11
Policy Version: severity-v1
"""

from src.risk.schemas import (
    AssessmentStatus,
    CoverageInfo,
    HazardRecord,
    SegmentAssessment,
    SegmentScoreResult,
    RouteSafetyResult,
)
from src.risk.severity import SeverityPolicy
from src.risk.aggregate import HazardAggregator, compute_iou, deduplicate_adjacent_segment_hazards
from src.risk.engine import DeterministicRiskEngine, compute_config_hash
from src.risk.comparison import RouteComparer, assessed_length_fraction, load_comparison_policy

__all__ = [
    "AssessmentStatus",
    "CoverageInfo",
    "HazardRecord",
    "SegmentAssessment",
    "SegmentScoreResult",
    "RouteSafetyResult",
    "SeverityPolicy",
    "HazardAggregator",
    "compute_iou",
    "deduplicate_adjacent_segment_hazards",
    "DeterministicRiskEngine",
    "compute_config_hash",
    "RouteComparer",
    "assessed_length_fraction",
    "load_comparison_policy",
]
