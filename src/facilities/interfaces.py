"""SafeRoute AI — Provider-Independent Facilities Interfaces.

Phase ID: PHASE_15
Follows PRD §4.7, TRD §4.7, ARCHITECTURE §8.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from src.facilities.schemas import FacilityResult


class FacilitiesProvider(ABC):
    """Abstract facilities provider interface.

    Isolates facility data sources (mock, Overpass/OSM) so upstream components
    depend only on this protocol. Facilities are context only and must never be
    consumed by the deterministic risk engine (Rule 11).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'mock_facilities', 'overpass')."""
        pass

    @abstractmethod
    def get_nearby_facilities(
        self,
        latitude: float,
        longitude: float,
        radius_m: Optional[float] = None,
        categories: Optional[List[str]] = None,
    ) -> FacilityResult:
        """Return nearby facilities honestly.

        Must never fabricate facilities. Empty/unknown results are reported with
        an explicit status (UNAVAILABLE), never filled in (Rule 20).
        """
        pass
