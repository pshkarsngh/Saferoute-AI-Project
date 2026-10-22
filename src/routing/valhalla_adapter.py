"""SafeRoute AI — Valhalla Live Routing Adapter.

Phase ID: PHASE_30
Implements the provider-independent :class:`RoutingProvider` protocol against the
public Valhalla / OpenStreetMap routing service (keyless, no account, no paid
tier).

Why a second provider exists
-----------------------------
The public OSRM demo server frequently returns a SINGLE route for long urban
corridors (verified live for Whitefield -> Bengaluru: ``routes=1`` even with
``alternatives=true``). Valhalla's ``alternates`` parameter returns several
genuinely different paths for the same corridor. Querying both providers and
merging the candidates therefore produces a real multi-route comparison
WITHOUT inventing a single route: every displayed route is one that a real
routing provider actually returned (master_rules.md Rule 10).

Invariants:
- Rule 10: Returns exactly the routes Valhalla returned; never synthesises or
  pads to a fixed count.
- Rule 8: A routing query does NOT grant imagery download rights.
- Rule 13: The public service needs no key, so no secret is involved. The base
  URL is configuration, not a credential.
- Rule 20: A provider failure is reported as a provider failure. It never
  degrades into "there is only one route".
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

#: Valhalla encodes its route shape as a polyline with 6 decimal places.
POLYLINE_PRECISION = 6


def decode_polyline(encoded: str, precision: int = POLYLINE_PRECISION) -> List[Tuple[float, float]]:
    """Decode an encoded polyline into ``[(lon, lat), ...]``.

    Google's polyline encoding format (used by Valhalla with precision 6):
    each coordinate is stored as a pair of zig-zag deltas. This is a pure
    decoder — it never alters or invents a coordinate.
    """
    if not encoded:
        return []
    factor = 10 ** precision
    coords: List[Tuple[float, float]] = []
    index = 0
    lat = 0
    lon = 0
    length = len(encoded)
    while index < length:
        for is_lon in (False, True):
            result = 0
            shift = 0
            while True:
                if index >= length:
                    return coords
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lon:
                lon += delta
            else:
                lat += delta
        coords.append((lon / factor, lat / factor))
    return coords


class ValhallaRoutingAdapter(RoutingProvider):
    """Live Valhalla routing provider adapter.

    Failures are surfaced through the provider-independent status vocabulary
    (``PROVIDER_ERROR`` / ``PROVIDER_TIMEOUT`` / ``RATE_LIMITED``), never as an
    empty-but-successful answer (Rule 20).
    """

    def __init__(
        self,
        base_url: str = "https://valhalla1.openstreetmap.de",
        costing: str = "auto",
        timeout_seconds: float = 8.0,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        alternates: int = 3,
        segmenter: Optional[RouteSegmenter] = None,
        user_agent: str = "SafeRouteAI/1.0 (RoadSafetyResearch; contact@saferoute.ai)",
    ):
        self.base_url = base_url.rstrip("/")
        self.costing = costing
        self.timeout = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.alternates = max(0, int(alternates))
        self.segmenter = segmenter or RouteSegmenter()
        self.user_agent = user_agent
        self._route_cache: Dict[str, Route] = {}
        # PHASE_31: the UI asks /api/routes for a geometry preview and then
        # /api/analyze for the assessment of the SAME corridor. Valhalla results
        # are deterministic for a fixed query (no live traffic input), so the
        # second request reuses the first response instead of paying the public
        # service again. Only successful responses are cached, so an outage is
        # never amplified by a stale hit (Rules 7, 10, 20).
        #
        # The window spans one full analysis plus the repeat the user runs next.
        # A fresh response would mint new route ids and thereby invalidate the
        # grounded explanation cache for otherwise identical evidence.
        self.ROUTE_CACHE_TTL_SECONDS = 600.0
        self.ROUTE_CACHE_MAX_ENTRIES = 32
        self._response_cache: Dict[str, Tuple[float, RouteResponse]] = {}

    @property
    def provider_name(self) -> str:
        return "valhalla"

    def _response_cache_key(self, request: RouteRequest) -> str:
        alternates = self.alternates if request.alternatives else 0
        return (
            f"{self.costing}|{request.origin.to_tuple()}|"
            f"{request.destination.to_tuple()}|{alternates}"
        )

    def _cache_put(self, key: str, response: RouteResponse) -> None:
        if len(self._response_cache) >= self.ROUTE_CACHE_MAX_ENTRIES:
            oldest = min(self._response_cache.items(), key=lambda kv: kv[1][0])[0]
            self._response_cache.pop(oldest, None)
        self._response_cache[key] = (time.monotonic(), response)

    # ------------------------------------------------------------------ #
    def _request_body(self, request: RouteRequest) -> Dict[str, Any]:
        return {
            "locations": [
                {
                    "lat": round(float(request.origin.latitude), 6),
                    "lon": round(float(request.origin.longitude), 6),
                },
                {
                    "lat": round(float(request.destination.latitude), 6),
                    "lon": round(float(request.destination.longitude), 6),
                },
            ],
            "costing": self.costing,
            "directions_options": {"units": "kilometers"},
            "language": "en-US",
            "alternates": self.alternates if request.alternatives else 0,
        }

    def get_routes(self, request: RouteRequest) -> RouteResponse:
        """Resolve driving routes between origin and destination via Valhalla."""
        cache_key = self._response_cache_key(request)
        cached = self._response_cache.get(cache_key)
        if cached is not None and time.monotonic() - cached[0] < self.ROUTE_CACHE_TTL_SECONDS:
            return cached[1]

        now_iso = datetime.now(timezone.utc).isoformat()
        req_id = f"val-{uuid.uuid4().hex[:8]}"

        body = self._request_body(request)
        encoded = urllib.parse.quote(json.dumps(body, separators=(",", ":")))
        endpoint = f"{self.base_url}/route?json={encoded}"

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

        trips = self._collect_trips(payload)
        if not trips:
            return RouteResponse(
                status=RoutingStatus.NO_ROUTES_FOUND,
                provider=self.provider_name,
                routes=[],
                request_id=req_id,
                retrieved_at=now_iso,
                limitations=["zero_routes_returned"],
                error_message=(
                    f"Valhalla returned status code: {payload.get('error', 'no path found')}"
                    if payload.get("error") else "Valhalla returned zero traversable driving routes."
                ),
            )

        parsed_routes: List[Route] = []
        for idx, trip in enumerate(trips):
            route = self._build_route(trip, idx, req_id)
            if route is None:
                continue
            parsed_routes.append(route)
            self._route_cache[route.route_id] = route

        limitations: List[str] = []
        if len(parsed_routes) < 4:
            limitations.append("fewer_than_four_routes_returned")

        response = RouteResponse(
            status=RoutingStatus.OK if parsed_routes else RoutingStatus.NO_ROUTES_FOUND,
            provider=self.provider_name,
            routes=parsed_routes,
            request_id=req_id,
            retrieved_at=now_iso,
            limitations=limitations,
        )
        if parsed_routes:
            self._cache_put(cache_key, response)
        return response

    # ------------------------------------------------------------------ #
    @staticmethod
    def _collect_trips(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return the main trip plus every alternate Valhalla actually returned."""
        trips: List[Dict[str, Any]] = []
        main = payload.get("trip")
        if isinstance(main, dict) and main.get("status") == 0:
            trips.append(main)
        for alt in payload.get("alternates") or []:
            if not isinstance(alt, dict):
                continue
            alt_trip = alt.get("trip")
            if isinstance(alt_trip, dict) and alt_trip.get("status") == 0:
                trips.append(alt_trip)
        return trips

    def _build_route(self, trip: Dict[str, Any], index: int, req_id: str) -> Optional[Route]:
        legs = trip.get("legs") or []
        if not legs:
            return None
        shape = ""
        duration_s = 0.0
        for leg in legs:
            shape += leg.get("shape") or ""
            duration_s += float((leg.get("summary") or {}).get("time") or 0.0)

        coords = decode_polyline(shape)
        if len(coords) < 2:
            return None

        summary = trip.get("summary") or {}
        distance_km = float(summary.get("length") or 0.0)
        if duration_s <= 0:
            duration_s = float(summary.get("time") or 0.0)

        route_id = f"rt-val-{req_id[-4:]}-{index:02d}"
        segments = self.segmenter.segment_from_coordinates(
            route_id=route_id,
            coordinates=coords,
            total_duration_s=duration_s,
        )

        # The provider's own distance is authoritative for the route length; the
        # segmented geometry only drives the per-segment assessment.
        distance_m = distance_km * 1000.0
        if distance_m <= 0:
            distance_m = sum(s.length_m for s in segments)

        return Route(
            route_id=route_id,
            provider=self.provider_name,
            summary=self._build_route_summary(trip, index),
            distance_m=distance_m,
            duration_s=duration_s,
            geometry=RouteGeometry(coordinates=coords),
            segments=segments,
            limitations=[],
        )

    @staticmethod
    def _build_route_summary(trip: Dict[str, Any], index: int) -> str:
        """Derive a corridor summary from the provider's own maneuver street names."""
        road_names: List[str] = []
        for leg in trip.get("legs") or []:
            for maneuver in leg.get("maneuvers") or []:
                for name in maneuver.get("street_names") or []:
                    if name and name not in road_names:
                        road_names.append(name)
        if road_names:
            main_road = max(set(road_names), key=road_names.count)
            return f"Route {index + 1} via {main_road}"
        return f"Route {index + 1} (Alternative {index})"

    # ------------------------------------------------------------------ #
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
                req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if isinstance(data, dict):
                        return data, RoutingStatus.OK, None
                    last_err = "Provider returned a non-object payload."
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}: {e.reason}"
                if e.code == 429:
                    return None, RoutingStatus.RATE_LIMITED, "Rate limit exceeded on the Valhalla service."
                if e.code == 400:
                    return None, RoutingStatus.NO_ROUTES_FOUND, f"Invalid coordinates or no route: {e.reason}"
            except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
                last_err = f"Network timeout/error: {str(e)}"
            except Exception as e:  # noqa: BLE001 - reported, never swallowed
                last_err = f"Unexpected communication error: {str(e)}"

            if attempt < self.max_retries:
                time.sleep(self.backoff_factor * (2 ** (attempt - 1)))

        if "timeout" in last_err.lower():
            return None, RoutingStatus.PROVIDER_TIMEOUT, (
                f"Request timed out after {self.max_retries} attempts ({last_err})")
        return None, RoutingStatus.PROVIDER_ERROR, (
            f"Valhalla request failed after {self.max_retries} attempts ({last_err})")
