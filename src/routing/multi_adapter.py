"""SafeRoute AI — Multi-Provider Route Composition.

Phase ID: PHASE_30
Combines the candidates returned by SEVERAL real routing providers into a
single, de-duplicated list of routes.

Why this exists
---------------
The public OSRM demo server frequently returns a single route for long urban
corridors (measured live: Whitefield -> Bengaluru returns ``routes=1`` even
with ``alternatives=true``), while the public Valhalla service returns several
genuinely different paths for the very same corridor. Composing both providers
produces a real multi-route comparison WITHOUT inventing anything.

Hard invariants (master_rules.md):
- Rule 10: Every route in the composed list was ACTUALLY returned by one of the
  configured providers. Nothing is synthesised, padded to four, or fabricated.
  When the providers return one route in total, exactly one route is emitted.
- Rule 20: A provider failure is disclosed as a limitation. It never removes
  the routes the other providers DID return, and it never rewrites a failure
  into "there is only one route".
- Rule 7: This module never computes or alters a safety score.
- The de-duplication is purely geometric: a route is dropped only when it
  follows essentially the same corridor as a route that is already kept.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import itertools
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.routing.interfaces import RoutingProvider
from src.routing.schemas import (
    Route,
    RouteGeometry,
    RouteRequest,
    RouteResponse,
    RouteSegment,
    RoutingStatus,
)

#: Two routes are the same corridor when this fraction of each route's points
#: lies within ``DEFAULT_CORRIDOR_TOLERANCE_M`` of the other route.
DEFAULT_CORRIDOR_OVERLAP = 0.80
DEFAULT_CORRIDOR_TOLERANCE_M = 60.0
DEFAULT_MAX_ROUTES = 4

EARTH_RADIUS_M = 6371000.0


def _to_local_xy(point: Tuple[float, float], lat_ref: float) -> Tuple[float, float]:
    """Project ``(lon, lat)`` to a local equirectangular plane (metres)."""
    lon, lat = point
    per_deg_lon = 111320.0 * math.cos(math.radians(lat_ref))
    return lon * per_deg_lon, lat * 110540.0


def _point_to_segment_m(
    p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]
) -> float:
    """Distance from ``p`` to segment ``a-b`` in the local projection."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx = bx - ax
    dy = by - ay
    len_sq = dx * dx + dy * dy
    t = 0.0 if len_sq == 0 else ((px - ax) * dx + (py - ay) * dy) / len_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _distance_to_polyline_m(
    p: Tuple[float, float], coords: Sequence[Tuple[float, float]], lat_ref: float
) -> float:
    """Minimum distance in metres from ``p`` to a polyline."""
    if not coords:
        return float("inf")
    if len(coords) == 1:
        pp = _to_local_xy(p, lat_ref)
        cp = _to_local_xy(coords[0], lat_ref)
        return math.hypot(pp[0] - cp[0], pp[1] - cp[1])
    best = float("inf")
    for i in range(1, len(coords)):
        a = _to_local_xy(coords[i - 1], lat_ref)
        b = _to_local_xy(coords[i], lat_ref)
        d = _point_to_segment_m(_to_local_xy(p, lat_ref), a, b)
        if d < best:
            best = d
    return best


def corridor_overlap(
    a: Sequence[Tuple[float, float]],
    b: Sequence[Tuple[float, float]],
    tolerance_m: float = DEFAULT_CORRIDOR_TOLERANCE_M,
) -> float:
    """How much two route geometries follow the same corridor (0.0 - 1.0).

    The value is the SMALLER of the two directional coverage fractions: the
    share of route A's points that lie within ``tolerance_m`` of route B and
    the share of route B's points that lie within ``tolerance_m`` of route A.
    Two different corridors through the same city score low; the same corridor
    routed by two different engines scores high.

    PHASE_31: the answer is computed with the SAME projection and the SAME
    point-to-segment distance as before, but the target polyline is projected
    once (instead of per query point) and indexed in a uniform grid keyed by
    the tolerance. A point can only be within tolerance of a segment whose
    bounding box, expanded by the tolerance, covers that point, so testing the
    point's own grid cell is exact — no approximate or shortened route
    comparison is introduced (Rules 7, 10).
    """
    if len(a) < 2 or len(b) < 2:
        return 0.0

    lat_ref = sum(pt[1] for pt in a) / len(a)
    per_deg_lon = 111320.0 * math.cos(math.radians(lat_ref))
    tolerance = float(tolerance_m)
    cell = max(tolerance, 100.0)

    def project(coords: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
        return [(lon * per_deg_lon, lat * 110540.0) for lon, lat in coords]

    def sample(coords: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
        if len(coords) <= 400:
            return list(coords)
        step = len(coords) / 400.0
        return [coords[int(i * step)] for i in range(400)]

    def build_grid(xy: List[Tuple[float, float]]):
        """Index each segment by every cell its tolerance-expanded box touches."""
        grid: Dict[Tuple[int, int], List[Tuple[float, float, float, float, float]]] = {}
        long_segments: List[Tuple[float, float, float, float, float]] = []
        for i in range(1, len(xy)):
            x0, y0 = xy[i - 1]
            x1, y1 = xy[i]
            dx, dy = x1 - x0, y1 - y0
            segment = (x0, y0, dx, dy, dx * dx + dy * dy)
            cx0 = math.floor((min(x0, x1) - tolerance) / cell)
            cx1 = math.floor((max(x0, x1) + tolerance) / cell)
            cy0 = math.floor((min(y0, y1) - tolerance) / cell)
            cy1 = math.floor((max(y0, y1) + tolerance) / cell)
            if (cx1 - cx0 + 1) * (cy1 - cy0 + 1) > 1024:
                # A very long segment (e.g. a 2-point fallback geometry) would
                # flood the grid; it is checked directly instead.
                long_segments.append(segment)
                continue
            for cx in range(cx0, cx1 + 1):
                for cy in range(cy0, cy1 + 1):
                    grid.setdefault((cx, cy), []).append(segment)
        return grid, long_segments

    def within_tolerance(px: float, py: float, grid, long_segments) -> bool:
        candidates = grid.get((math.floor(px / cell), math.floor(py / cell)), ())
        for ax, ay, dx, dy, len_sq in itertools.chain(candidates, long_segments):
            if len_sq == 0:
                if math.hypot(px - ax, py - ay) <= tolerance:
                    return True
                continue
            t = ((px - ax) * dx + (py - ay) * dy) / len_sq
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            if math.hypot(px - (ax + t * dx), py - (ay + t * dy)) <= tolerance:
                return True
        return False

    a_xy = project(a)
    b_xy = project(b)
    a_grid, a_long = build_grid(a_xy)
    b_grid, b_long = build_grid(b_xy)

    def coverage(points: Sequence[Tuple[float, float]], grid, long_segments) -> float:
        points = sample(points)
        inside = 0
        for px, py in points:
            if within_tolerance(px, py, grid, long_segments):
                inside += 1
        return inside / len(points) if points else 0.0

    return min(coverage(a_xy, b_grid, b_long), coverage(b_xy, a_grid, a_long))


class MultiProviderRoutingAdapter(RoutingProvider):
    """Routing adapter that composes several real routing providers."""

    def __init__(
        self,
        adapters: Sequence[RoutingProvider],
        max_routes: int = DEFAULT_MAX_ROUTES,
        corridor_overlap_threshold: float = DEFAULT_CORRIDOR_OVERLAP,
        corridor_tolerance_m: float = DEFAULT_CORRIDOR_TOLERANCE_M,
    ):
        if not adapters:
            raise ValueError("MultiProviderRoutingAdapter requires at least one provider")
        self.adapters = list(adapters)
        self.max_routes = max(1, int(max_routes))
        self.corridor_overlap_threshold = float(corridor_overlap_threshold)
        self.corridor_tolerance_m = float(corridor_tolerance_m)
        # route_id -> owning adapter, so the protocol lookups stay correct.
        self._owners: Dict[str, RoutingProvider] = {}

    @property
    def provider_name(self) -> str:
        return "multi"

    @property
    def provider_names(self) -> List[str]:
        return [a.provider_name for a in self.adapters]

    # ------------------------------------------------------------------ #
    def get_routes(self, request: RouteRequest) -> RouteResponse:
        """Query every configured provider and compose the returned routes."""
        now_iso = datetime.now(timezone.utc).isoformat()
        request_id = f"multi-{int(datetime.now(timezone.utc).timestamp() * 1000):x}"

        responses = self._query_all(request)

        limitations: List[str] = []
        routes: List[Route] = []
        providers_used: List[str] = []

        for adapter, response in zip(self.adapters, responses):
            if response is None:
                limitations.append(f"provider_unavailable_{adapter.provider_name}")
                continue
            if response.status != RoutingStatus.OK:
                limitations.append(f"provider_status_{adapter.provider_name}_{response.status.value}")
                if response.error_message:
                    limitations.append(
                        f"{adapter.provider_name}_error: {response.error_message}")
                continue
            if not response.routes:
                limitations.append(f"provider_returned_no_routes_{adapter.provider_name}")
                continue
            providers_used.append(adapter.provider_name)
            for route in response.routes:
                self._owners[route.route_id] = adapter
                routes.append(route)

        if not routes:
            return RouteResponse(
                status=RoutingStatus.NO_ROUTES_FOUND,
                provider=self.provider_name,
                routes=[],
                request_id=request_id,
                retrieved_at=now_iso,
                limitations=limitations + ["zero_routes_returned"],
                error_message="None of the configured routing providers returned a route.",
            )

        merged = self._merge(routes)

        if len(merged) < self.max_routes:
            limitations.append("fewer_than_four_routes_returned")

        return RouteResponse(
            status=RoutingStatus.OK,
            provider=self.provider_name,
            routes=merged,
            request_id=request_id,
            retrieved_at=now_iso,
            limitations=limitations,
            providers=providers_used,
        )

    # ------------------------------------------------------------------ #
    def _query_all(self, request: RouteRequest) -> List[Optional[RouteResponse]]:
        """Query every provider in parallel; a failure never aborts the others."""

        def run(adapter: RoutingProvider) -> Optional[RouteResponse]:
            try:
                return adapter.get_routes(request)
            except Exception:  # noqa: BLE001 - a provider failure must not fail the request
                return None

        if len(self.adapters) == 1:
            return [run(self.adapters[0])]
        with ThreadPoolExecutor(max_workers=len(self.adapters)) as pool:
            return list(pool.map(run, self.adapters))

    def _merge(self, routes: List[Route]) -> List[Route]:
        """De-duplicate by corridor and cap the list at ``max_routes``."""
        kept: List[Route] = []
        for route in routes:
            if len(kept) >= self.max_routes:
                break
            if self._is_duplicate(route, kept):
                continue
            kept.append(route)
        return kept

    def _is_duplicate(self, route: Route, kept: List[Route]) -> bool:
        """Whether ``route`` follows essentially the same corridor as a kept one."""
        coords = route.geometry.coordinates
        if len(coords) < 2:
            return False
        for existing in kept:
            if corridor_overlap(
                coords,
                existing.geometry.coordinates,
                tolerance_m=self.corridor_tolerance_m,
            ) >= self.corridor_overlap_threshold:
                return True
        return False

    # ------------------------------------------------------------------ #
    def get_route_geometry(self, route_id: str) -> Optional[RouteGeometry]:
        owner = self._owners.get(route_id)
        if owner is not None:
            return owner.get_route_geometry(route_id)
        for adapter in self.adapters:
            geometry = adapter.get_route_geometry(route_id)
            if geometry is not None:
                return geometry
        return None

    def get_segment_metadata(self, route_id: str) -> List[RouteSegment]:
        owner = self._owners.get(route_id)
        if owner is not None:
            return owner.get_segment_metadata(route_id)
        for adapter in self.adapters:
            segments = adapter.get_segment_metadata(route_id)
            if segments:
                return segments
        return []

    def to_dict(self) -> Dict[str, Any]:
        """Non-secret description of the composed providers (for /api/health)."""
        return {
            "provider": self.provider_name,
            "providers": self.provider_names,
            "max_routes": self.max_routes,
            "corridor_overlap_threshold": self.corridor_overlap_threshold,
        }
