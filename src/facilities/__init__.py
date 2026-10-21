"""SafeRoute AI — Facilities Lookup Service package (PHASE_15, PHASE_29).

Facilities are context only and never enter the hazard score (Rule 11).
"""

from src.facilities.geometry import (
    distance_to_polylines_m,
    nearest_point_on_polyline,
    normalise_polylines,
    polylines_bbox,
)
from src.facilities.interfaces import FacilitiesProvider
from src.facilities.mock_provider import MockFacilitiesProvider
from src.facilities.overpass_provider import OverpassFacilitiesProvider
from src.facilities.schemas import (
    DISTANCE_ROAD,
    DISTANCE_STRAIGHT_LINE,
    OSM_ATTRIBUTES_NOTE,
    ROAD_TRAVEL_TIME_UNAVAILABLE_NOTE,
    Facility,
    FacilityResult,
    FacilityStatus,
)
from src.facilities.service import (
    FacilitiesService,
    create_facilities_provider,
    load_facilities_config,
)

__version__ = "facilities-v2"

__all__ = [
    "FacilitiesProvider",
    "Facility",
    "FacilityResult",
    "FacilityStatus",
    "DISTANCE_ROAD",
    "DISTANCE_STRAIGHT_LINE",
    "OSM_ATTRIBUTES_NOTE",
    "ROAD_TRAVEL_TIME_UNAVAILABLE_NOTE",
    "MockFacilitiesProvider",
    "OverpassFacilitiesProvider",
    "FacilitiesService",
    "create_facilities_provider",
    "load_facilities_config",
    "distance_to_polylines_m",
    "nearest_point_on_polyline",
    "normalise_polylines",
    "polylines_bbox",
]
