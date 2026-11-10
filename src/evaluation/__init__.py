"""SafeRoute AI — Phase 42 Independent Detector Evaluation.

This package measures the *serving* YOLO11 detector. It is deliberately
separate from ``src/risk`` and must never modify the production scoring engine,
the serving checkpoint, or the production inference configuration.

Modules
-------
matching               Class-aware IoU matching of predictions to ground truth.
metrics                AP50 / AP50-95, precision / recall, operational metrics.
confidence_intervals   Wilson intervals and session-clustered bootstrap.
dataset_validation     Dataset parsing, label validation, content hashing.
leakage                Session/scene/duplicate leakage checks.
evaluator              Stage A + Stage B orchestration and acceptance gates.
route_replay           Offline ground-truth vs predicted route comparison.
"""

from .confidence_intervals import (
    BootstrapCI,
    clustered_bootstrap_ci,
    insufficient_sample,
    wilson_interval,
)
from .matching import (
    BoxValidationError,
    DatasetMatch,
    GroundTruthBox,
    MatchingError,
    PredictionBox,
    compute_iou,
    match_dataset,
    match_image,
    validate_bbox_norm,
)
from .metrics import (
    APMetrics,
    CountMetrics,
    average_precision,
    compute_ap_metrics,
    compute_counts,
    deduplicate_frame_false_positives,
    false_positives_per_km,
    group_metrics,
    miss_rate,
)

__all__ = [
    "APMetrics",
    "BootstrapCI",
    "BoxValidationError",
    "CountMetrics",
    "DatasetMatch",
    "GroundTruthBox",
    "MatchingError",
    "PredictionBox",
    "average_precision",
    "clustered_bootstrap_ci",
    "compute_ap_metrics",
    "compute_counts",
    "compute_iou",
    "deduplicate_frame_false_positives",
    "false_positives_per_km",
    "group_metrics",
    "insufficient_sample",
    "match_dataset",
    "match_image",
    "miss_rate",
    "validate_bbox_norm",
    "wilson_interval",
]
