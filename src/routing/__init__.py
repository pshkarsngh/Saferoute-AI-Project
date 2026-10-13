"""SafeRoute AI — Provider-Independent Routing Package.

Phase ID: PHASE_13
Architecture: Provider-independent routing adapter interface and segmentation.
"""

from src.routing.schemas import (
    Coordinate,
    Route,
    RouteGeometry,
    RouteRequest,
    RouteResponse,
    RouteSegment,
    RoutingStatus,
)
from src.routing.interfaces import RoutingProvider
from src.routing.segmentation import (
    RouteSegmenter,
    compute_linestring_length_m,
    haversine_distance_m,
)
from src.routing.mock_adapter import MockRoutingAdapter
from src.routing.osrm_adapter import OSRMRoutingAdapter
from src.routing.adapter import create_routing_adapter, load_routing_config

__all__ = [
    "Coordinate",
    "Route",
    "RouteGeometry",
    "RouteRequest",
    "RouteResponse",
    "RouteSegment",
    "RoutingStatus",
    "RoutingProvider",
    "RouteSegmenter",
    "compute_linestring_length_m",
    "haversine_distance_m",
    "MockRoutingAdapter",
    "OSRMRoutingAdapter",
    "create_routing_adapter",
    "load_routing_config",
]
