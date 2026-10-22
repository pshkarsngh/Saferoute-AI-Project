"""SafeRoute AI — Routing Domain Data Contracts & Schemas.

Phase ID: PHASE_13
Follows TRD §10, ARCHITECTURE §8, master_rules.md Rules 8, 10, 13.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RoutingStatus(str, Enum):
    """Categorical outcome of route query."""
    OK = "ok"
    NO_ROUTES_FOUND = "no_routes_found"
    PROVIDER_ERROR = "provider_error"
    PROVIDER_TIMEOUT = "provider_timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_REQUEST = "invalid_request"


@dataclass(frozen=True)
class Coordinate:
    """Geographic coordinate (latitude, longitude)."""
    latitude: float
    longitude: float

    def to_tuple(self) -> Tuple[float, float]:
        """Return (lat, lon) tuple."""
        return (round(float(self.latitude), 6), round(float(self.longitude), 6))

    def to_lon_lat_tuple(self) -> Tuple[float, float]:
        """Return (lon, lat) tuple matching GeoJSON convention."""
        return (round(float(self.longitude), 6), round(float(self.latitude), 6))

    def to_dict(self) -> Dict[str, float]:
        return {
            "latitude": round(float(self.latitude), 6),
            "longitude": round(float(self.longitude), 6),
        }


@dataclass(frozen=True)
class RouteGeometry:
    """GeoJSON-compatible LineString geometry representation."""
    type: str = "LineString"
    coordinates: List[Tuple[float, float]] = field(default_factory=list)  # [(lon, lat), ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "coordinates": [[round(float(c[0]), 6), round(float(c[1]), 6)] for c in self.coordinates],
        }


@dataclass
class RouteSegment:
    """Decomposed route segment with stable identifier (FR-R4, TRD §10.1)."""
    segment_id: str
    route_id: str
    sequence: int
    length_m: float
    duration_s: float
    start_coord: Coordinate
    end_coord: Coordinate
    geometry: RouteGeometry
    road_name: Optional[str] = None
    instruction: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "route_id": self.route_id,
            "sequence": self.sequence,
            "length_m": round(float(self.length_m), 1),
            "duration_s": round(float(self.duration_s), 1),
            "start_coord": self.start_coord.to_dict(),
            "end_coord": self.end_coord.to_dict(),
            "geometry": self.geometry.to_dict(),
            "road_name": self.road_name,
            "instruction": self.instruction,
        }


@dataclass
class Route:
    """Complete route record emitted by provider adapter."""
    route_id: str
    provider: str
    summary: str
    distance_m: float
    duration_s: float
    geometry: RouteGeometry
    segments: List[RouteSegment] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "provider": self.provider,
            "summary": self.summary,
            "distance_m": round(float(self.distance_m), 1),
            "duration_s": round(float(self.duration_s), 1),
            "geometry": self.geometry.to_dict(),
            "segments_count": len(self.segments),
            "segments": [s.to_dict() for s in self.segments],
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class RouteRequest:
    """Standardized input request for route search."""
    origin: Coordinate
    destination: Coordinate
    alternatives: bool = True
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResponse:
    """Standardized response emitted by provider-independent routing adapter."""
    status: RoutingStatus
    provider: str
    routes: List[Route] = field(default_factory=list)
    request_id: str = ""
    retrieved_at: str = ""
    limitations: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    # PHASE_30: the routing providers that actually contributed routes. Purely
    # additive — a single-provider response simply carries one name.
    providers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "provider": self.provider,
            "providers": list(self.providers),
            "routes_count": len(self.routes),
            "routes": [r.to_dict() for r in self.routes],
            "request_id": self.request_id,
            "retrieved_at": self.retrieved_at,
            "limitations": list(self.limitations),
            "error_message": self.error_message,
        }
