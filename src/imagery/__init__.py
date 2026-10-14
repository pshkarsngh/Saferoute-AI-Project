"""SafeRoute AI — Permitted Imagery Acquisition Package.

Phase ID: PHASE_14
Architecture: Rule 8 permitted source adapter, spatial matching, and staleness tracking.
"""

from src.imagery.schemas import (
    ImageRef,
    ImageryResult,
    ImageryStatus,
    ImageryUnavailable,
)
from src.imagery.interfaces import ImageryProvider
from src.imagery.staleness import StalenessEvaluator
from src.imagery.matcher import (
    SegmentImageryMatcher,
    point_to_segment_distance_m,
)
from src.imagery.adapter import PermittedImageryAdapter
from src.imagery.mapillary_provider import MapillaryHttp, MapillaryImageryProvider

__all__ = [
    "ImageRef",
    "ImageryResult",
    "ImageryStatus",
    "ImageryUnavailable",
    "ImageryProvider",
    "StalenessEvaluator",
    "SegmentImageryMatcher",
    "point_to_segment_distance_m",
    "PermittedImageryAdapter",
    "MapillaryHttp",
    "MapillaryImageryProvider",
]
