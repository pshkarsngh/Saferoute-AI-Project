"""SafeRoute AI — Open Source Routing Machine (OSRM) Live Adapter.

Phase ID: PHASE_13
Implements provider-independent RoutingProvider protocol using public OSRM / OpenStreetMap.
Follows TRD §10, ARCHITECTURE §8, master_rules.md Rules 8, 10, 13.
"""

from datetime import datetime, timezone
import json
import logging
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
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

logger = logging.getLogger(__name__)


class OSRMRoutingAdapter(RoutingProvider):
    """Live OSRM routing provider adapter.
    
    Invariants:
    - Rule 10: Returns exactly the routes returned by OSRM; never synthesises/pads.
    - Rule 8: Routing queries do NOT grant imagery download rights.
    - Rule 13: Secrets/credentials (if any) managed strictly via environment.
    """

    def __init__(
        self,
        base_url: str = "https://router.project-osrm.org",
        profile: str = "driving",
        timeout_seconds: float = 5.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        segmenter: Optional[RouteSegmenter] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.profile = profile
        self.timeout = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.segmenter = segmenter or RouteSegmenter()
        self._route_cache: Dict[str, Route] = {}

    @property
    def provider_name(self) -> str:
        return "osrm"

    def get_routes(self, request: RouteRequest) -> RouteResponse:
        """Resolve driving routes between origin and destination via OSRM API."""
        now_iso = datetime.now(timezone.utc).isoformat()
        req_id = f"osrm-{uuid.uuid4().hex[:8]}"

        lon1, lat1 = request.origin.longitude, request.origin.latitude
        lon2, lat2 = request.destination.longitude, request.destination.latitude

        # Format: /route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson&alternatives=true&steps=true
        query_params = {
            "overview": "full",
            "geometries": "geojson",
            "alternatives": "true" if request.alternatives else "false",
            "steps": "true",
        }
        encoded_params = urllib.parse.urlencode(query_params)
        endpoint = f"{self.base_url}/route/v1/{self.profile}/{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}?{encoded_params}"

        payload, status, err_msg = self._fetch_with_retry(endpoint)

        if status != RoutingStatus.OK or not payload:
            return RouteResponse(
                status=status,
                provider=self.provider_name,
                routes=[],
                request_id=req_id,
                retrieved_at=now_iso,
                limitations=[f"provider_error_{status.value}"],
                error_message=err_msg,
            )

        code = payload.get("code")
        if code != "Ok":
            return RouteResponse(
                status=RoutingStatus.NO_ROUTES_FOUND,
                provider=self.provider_name,
                routes=[],
                request_id=req_id,
                retrieved_at=now_iso,
                limitations=["zero_routes_returned"],
                error_message=f"OSRM returned status code: {code} ({payload.get('message', 'No path found')})",
            )

        raw_routes = payload.get("routes", [])
        if not raw_routes:
            return RouteResponse(
                status=RoutingStatus.NO_ROUTES_FOUND,
                provider=self.provider_name,
                routes=[],
                request_id=req_id,
                retrieved_at=now_iso,
                limitations=["zero_routes_returned"],
                error_message="OSRM returned zero traversable driving routes.",
            )

        # Parse genuine returned routes (Rule 10)
        parsed_routes: List[Route] = []
        for idx, r_data in enumerate(raw_routes):
            route_id = f"rt-osrm-{req_id[-4:]}-{idx:02d}"
            geom_coords = r_data.get("geometry", {}).get("coordinates", [])
            route_geom = RouteGeometry(coordinates=geom_coords)

            # Extract steps across legs for segmentation
            steps: List[Dict[str, Any]] = []
            for leg in r_data.get("legs", []):
                steps.extend(leg.get("steps", []))

            # Segment the route into assessable units with stable IDs
            segments = self.segmenter.segment_from_steps(
                route_id=route_id,
                steps=steps,
                fallback_coordinates=geom_coords,
            )

            distance_m = float(r_data.get("distance", sum(s.length_m for s in segments)))
            duration_s = float(r_data.get("duration", sum(s.duration_s for s in segments)))
            summary = self._build_route_summary(steps, idx)

            parsed_route = Route(
                route_id=route_id,
                provider=self.provider_name,
                summary=summary,
                distance_m=distance_m,
                duration_s=duration_s,
                geometry=route_geom,
                segments=segments,
                limitations=[],
            )
            parsed_routes.append(parsed_route)
            self._route_cache[route_id] = parsed_route

        limitations: List[str] = []
        if len(parsed_routes) < 4:
            limitations.append("fewer_than_four_routes_returned")

        return RouteResponse(
            status=RoutingStatus.OK,
            provider=self.provider_name,
            routes=parsed_routes,
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

    def _fetch_with_retry(self, url: str) -> Tuple[Optional[Dict[str, Any]], RoutingStatus, Optional[str]]:
        """Bounded retries with exponential backoff for network queries."""
        last_err = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "SafeRouteAI/1.0 (RoadSafetyResearch; contact@saferoute.ai)"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data, RoutingStatus.OK, None
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}: {e.reason}"
                if e.code == 429:
                    return None, RoutingStatus.RATE_LIMITED, "Rate limit exceeded on OSRM API."
                if e.code == 400:
                    return None, RoutingStatus.NO_ROUTES_FOUND, f"Invalid coordinates or no route: {e.reason}"
            except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
                last_err = f"Network timeout/error: {str(e)}"
            except Exception as e:
                last_err = f"Unexpected communication error: {str(e)}"

            if attempt < self.max_retries:
                time.sleep(self.backoff_factor * (2 ** (attempt - 1)))

        if "timeout" in last_err.lower():
            return None, RoutingStatus.PROVIDER_TIMEOUT, f"Request timed out after {self.max_retries} attempts ({last_err})"
        return None, RoutingStatus.PROVIDER_ERROR, f"OSRM request failed after {self.max_retries} attempts ({last_err})"

    def _build_route_summary(self, steps: List[Dict[str, Any]], index: int) -> str:
        """Derive meaningful corridor summary from primary step road names."""
        road_names = [
            s.get("name") for s in steps
            if s.get("name") and s.get("name") not in ["", "Unnamed Road"]
        ]
        if road_names:
            # Pick the top unique road name that appears most frequently
            main_road = max(set(road_names), key=road_names.count)
            return f"Route {index + 1} via {main_road}"
        return f"Route {index + 1} (Alternative {index})"
