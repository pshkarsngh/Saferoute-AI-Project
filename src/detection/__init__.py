"""SafeRoute AI — Object Detection & Hazard Inference Package.

Phase ID: PHASE_10
Version: detect-v1
"""

from src.detection.detector import (
    HazardDetector,
    MODEL_VERSION,
    SUPPORTED_CLASSES,
    __version__,
)
from src.detection.schemas import (
    DetectionRecord,
    DetectionStatus,
    ImageDetectionResult,
)

__all__ = [
    "HazardDetector",
    "DetectionRecord",
    "DetectionStatus",
    "ImageDetectionResult",
    "MODEL_VERSION",
    "SUPPORTED_CLASSES",
    "__version__",
]
