"""SafeRoute AI — Deterministic Mock Routing Adapter.

Phase ID: PHASE_13
Provides 100% reproducible, offline routing responses from realistic fixtures.
Follows TRD §10, ARCHITECTURE §8, master_rules.md Rules 10, 14.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from src.routing.interfaces import RoutingProvider
from src.routing.schemas import (
    Coordinate,
    Route,
    RouteGeometry,
    RouteRequest,
    RouteResponse,
    RouteSegment,
    RoutingStatus,
)
from src.routing.segmentation import RouteSegmenter


class MockRoutingAdapter(RoutingProvider):
    """Deterministic, fixture-based mock provider for test suite and offline operation.
    
    Invariants:
    - Rule 10: Never pads routes to a fixed count.
    - Deterministic responses for zero-routes, fewer-than-four, errors, and timeouts.
    """

    def __init__(
        self,
        mode: str = "standard_two_routes",
        segmenter: Optional[RouteSegmenter] = None,
    ):
        """Initialize mock adapter.
        
        Args:
            mode: One of 'standard_two_routes', 'single_route', 'three_routes',
                  'zero_routes', 'timeout', 'provider_error', 'rate_limited'.
            segmenter: Optional custom segmenter instance.
        """
        self.mode = mode
        self.segmenter = segmenter or RouteSegmenter()
        self._route_cache: Dict[str, Route] = {}

    @property
    def provider_name(self) -> str:
        return "mock_routing"

    def set_mode(self, mode: str) -> None:
        """Switch mock operational mode for test scenarios."""
        self.mode = mode

    def get_routes(self, request: RouteRequest) -> RouteResponse:
        """Emulate route resolution per configured mock mode."""
        now_iso = datetime.now(timezone.utc).isoformat()
        req_id = f"mock-req-{uuid.uuid4().hex[:8]}"

        # Edge Case: Timeout simulation
        if self.mode == "timeout":
            return RouteResponse(
                status=RoutingStatus.PROVIDER_TIMEOUT,
                provider=self.provider_name,
                routes=[],
                request_id=req_id,
                retrieved_at=now_iso,
                limitations=["routing_request_timed_out_after_max_retries"],
                error_message="Mock provider simulated network timeout after 3 bounded retries.",
            )

        # Edge Case: Provider Error simulation
        if self.mode == "provider_error":
            return RouteResponse(
                status=RoutingStatus.PROVIDER_ERROR,
                provider=self.provider_name,
                routes=[],
                request_id=req_id,
                retrieved_at=now_iso,
                limitations=["routing_provider_service_unreachable"],
                error_message="Mock provider simulated HTTP 500 upstream failure.",
            )

        # Edge Case: Rate limit simulation
        if self.mode == "rate_limited":
            return RouteResponse(
                status=RoutingStatus.RATE_LIMITED,
                provider=self.provider_name,
                routes=[],
                request_id=req_id,
                retrieved_at=now_iso,
                limitations=["rate_limit_exceeded"],
                error_message="Mock provider simulated HTTP 429 quota exhausted.",
            )

        # Edge Case: Zero routes returned (Rule 10)
        if self.mode == "zero_routes":
            return RouteResponse(
                status=RoutingStatus.NO_ROUTES_FOUND,
                provider=self.provider_name,
                routes=[],
                request_id=req_id,
                retrieved_at=now_iso,
                limitations=["zero_routes_returned"],
                error_message="No traversable driving path found between coordinates.",
            )

        # Build realistic fixture geometries based on coordinates
        routes = self._generate_fixture_routes(request.origin, request.destination)
        self._route_cache = {r.route_id: r for r in routes}

        limitations: List[str] = []
        if len(routes) < 4:
            limitations.append("fewer_than_four_routes_returned")

        return RouteResponse(
            status=RoutingStatus.OK,
            provider=self.provider_name,
            routes=routes,
            request_id=req_id,
            retrieved_at=now_iso,
            limitations=limitations,
        )

    def get_route_geometry(self, route_id: str) -> Optional[RouteGeometry]:
        route = self._route_cache.get(route_id)
        return route.geometry if route else None

    def get_segment_metadata(self, route_id: str) -> List[RouteSegment]:
        route = self._route_cache.get(route_id)
        return list(route.segments) if route else []

    def _generate_fixture_routes(self, origin: Coordinate, destination: Coordinate) -> List[Route]:
        """Generate realistic route geometry and segmentations between origin and destination."""
        lat1, lon1 = origin.latitude, origin.longitude
        lat2, lon2 = destination.latitude, destination.longitude

        # Route 1: Direct / Highway Corridor
        mid_lat1 = (lat1 + lat2) / 2.0
        mid_lon1 = (lon1 + lon2) / 2.0
        coords_1 = [
            (lon1, lat1),
            ((lon1 * 2 + mid_lon1) / 3.0, (lat1 * 2 + mid_lat1) / 3.0),
            (mid_lon1, mid_lat1),
            ((mid_lon1 + lon2 * 2) / 3.0, (mid_lat1 + lat2 * 2) / 3.0),
            (lon2, lat2),
        ]
        geom_1 = RouteGeometry(coordinates=coords_1)
        r1_id = "route_mock_alpha"
        segments_1 = self.segmenter.segment_from_coordinates(
            route_id=r1_id,
            coordinates=coords_1,
            total_duration_s=600.0,
        )
        dist_1 = sum(s.length_m for s in segments_1)

        route_1 = Route(
            route_id=r1_id,
            provider=self.provider_name,
            summary="Primary Corridor via Central Expressway",
            distance_m=dist_1,
            duration_s=600.0,
            geometry=geom_1,
            segments=segments_1,
            limitations=[],
        )

        if self.mode == "single_route":
            return [route_1]

        # Route 2: Secondary / Arterial Road (Alternative 1)
        mid_lat2 = mid_lat1 + 0.005
        mid_lon2 = mid_lon1 - 0.005
        coords_2 = [
            (lon1, lat1),
            (lon1 + (mid_lon2 - lon1) * 0.5, lat1 + (mid_lat2 - lat1) * 0.5),
            (mid_lon2, mid_lat2),
            (mid_lon2 + (lon2 - mid_lon2) * 0.5, mid_lat2 + (lat2 - mid_lat2) * 0.5),
            (lon2, lat2),
        ]
        geom_2 = RouteGeometry(coordinates=coords_2)
        r2_id = "route_mock_beta"
        segments_2 = self.segmenter.segment_from_coordinates(
            route_id=r2_id,
            coordinates=coords_2,
            total_duration_s=750.0,
        )
        dist_2 = sum(s.length_m for s in segments_2)

        route_2 = Route(
            route_id=r2_id,
            provider=self.provider_name,
            summary="Alternative Route via Western Ring Road",
            distance_m=dist_2,
            duration_s=750.0,
            geometry=geom_2,
            segments=segments_2,
            limitations=[],
        )

        if self.mode == "standard_two_routes":
            return [route_1, route_2]

        # Route 3: Scenic / Local Road (Alternative 2)
        mid_lat3 = mid_lat1 - 0.006
        mid_lon3 = mid_lon1 + 0.006
        coords_3 = [
            (lon1, lat1),
            (mid_lon3, mid_lat3),
            (lon2, lat2),
        ]
        geom_3 = RouteGeometry(coordinates=coords_3)
        r3_id = "route_mock_gamma"
        segments_3 = self.segmenter.segment_from_coordinates(
            route_id=r3_id,
            coordinates=coords_3,
            total_duration_s=900.0,
        )
        dist_3 = sum(s.length_m for s in segments_3)

        route_3 = Route(
            route_id=r3_id,
            provider=self.provider_name,
            summary="Southern Arterial Bypass",
            distance_m=dist_3,
            duration_s=900.0,
            geometry=geom_3,
            segments=segments_3,
            limitations=[],
        )

        return [route_1, route_2, route_3]
