"""SafeRoute AI — Provider-Independent Facilities Interfaces.

Phase ID: PHASE_15, extended in PHASE_29 (corridor lookups).

Follows PRD §4.7, TRD §4.7, ARCHITECTURE §8.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

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

    @abstractmethod
    def get_facilities_in_bbox(
        self,
        bbox: Tuple[float, float, float, float],
        categories: Optional[List[str]] = None,
    ) -> FacilityResult:
        """Return the facilities inside a bounding box ``(south, west, north, east)``.

        Used for route-corridor lookups, where the searched area is a long
        narrow band rather than a circle.

        Contract notes:
        * ``distance_m`` is measured as a straight-line distance from the
          CENTRE of the bounding box. The caller (``FacilitiesService``)
          recomputes the distance against the actual query geometry, so this
          intermediate value is never presented to a user as "distance to the
          route".
        * The result carries the same honest status vocabulary as
          :meth:`get_nearby_facilities` (Rule 20).
        """
        pass
