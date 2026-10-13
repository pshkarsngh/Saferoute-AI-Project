"""SafeRoute AI — Facilities Lookup Service package (PHASE_15).

Facilities are context only and never enter the hazard score (Rule 11).
"""

from src.facilities.interfaces import FacilitiesProvider
from src.facilities.mock_provider import MockFacilitiesProvider
from src.facilities.overpass_provider import OverpassFacilitiesProvider
from src.facilities.schemas import Facility, FacilityResult, FacilityStatus
from src.facilities.service import (
    FacilitiesService,
    create_facilities_provider,
    load_facilities_config,
)

__version__ = "facilities-v1"

__all__ = [
    "FacilitiesProvider",
    "Facility",
    "FacilityResult",
    "FacilityStatus",
    "MockFacilitiesProvider",
    "OverpassFacilitiesProvider",
    "FacilitiesService",
    "create_facilities_provider",
    "load_facilities_config",
]
