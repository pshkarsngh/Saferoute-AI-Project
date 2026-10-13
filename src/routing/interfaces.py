"""SafeRoute AI — Provider-Independent Routing Protocols & Interfaces.

Phase ID: PHASE_13
Follows TRD §10.1, ARCHITECTURE §8.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from src.routing.schemas import (
    RouteGeometry,
    RouteRequest,
    RouteResponse,
    RouteSegment,
)


class RoutingProvider(ABC):
    """Abstract provider-independent routing interface matching TRD §10.1 & ARCHITECTURE §8.
    
    Isolates routing implementations (OSRM, Mapbox, Mock) so upstream components
    depend strictly on this protocol and can swap providers seamlessly.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'osrm', 'mock')."""
        pass

    @abstractmethod
    def get_routes(self, request: RouteRequest) -> RouteResponse:
        """Resolve origin/destination and return genuine alternative routes (Rule 10).
        
        Hard Invariant: Must return ONLY routes returned by provider. Never pad to 4.
        """
        pass

    @abstractmethod
    def get_route_geometry(self, route_id: str) -> Optional[RouteGeometry]:
        """Fetch full line geometry for a specified route ID."""
        pass

    @abstractmethod
    def get_segment_metadata(self, route_id: str) -> List[RouteSegment]:
        """Fetch decomposed assessable segments with stable IDs for a route."""
        pass
