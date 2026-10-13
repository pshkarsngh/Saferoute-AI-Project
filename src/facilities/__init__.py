"""SafeRoute AI — Facilities Lookup Service package (PHASE_15).

Facilities are context only and never enter the hazard score (Rule 11).
"""

from src.facilities.interfaces import FacilitiesProvider
from src.facilities.schemas import Facility, FacilityResult, FacilityStatus

__version__ = "facilities-v1"

__all__ = [
    "FacilitiesProvider",
    "Facility",
    "FacilityResult",
    "FacilityStatus",
]
