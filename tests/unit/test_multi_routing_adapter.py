"""SafeRoute AI — Multi-provider routing composition & Valhalla decoding.

Phase ID: PHASE_30
Covers the second routing provider: composing candidates from several REAL
providers, de-duplicating them by corridor geometry, and decoding the Valhalla
polyline shape.

The rules these tests defend (master_rules.md):
- Rule 10: only routes a provider actually returned are emitted. A single
  returned route stays a single route — it is never padded to four.
- Rule 20: a provider failure is disclosed as a limitation; it never removes
  the routes the OTHER providers returned.
- Rule 7: nothing here computes or alters a safety score.
"""

import unittest
from typing import List, Optional

from src.routing.multi_adapter import MultiProviderRoutingAdapter, corridor_overlap
from src.routing.schemas import (
    Coordinate,
    Route,
    RouteGeometry,
    RouteRequest,
    RouteResponse,
    RoutingStatus,
)
from src.routing.valhalla_adapter import decode_polyline


def _line(offset: float, count: int = 12) -> List[tuple]:
    """A straight-ish polyline shifted east by ``offset`` degrees."""
    return [(77.60 + offset + 0.002 * i, 12.97 + 0.001 * i) for i in range(count)]


def _route(route_id: str, provider: str, coords: List[tuple],
           distance_m: float = 5000.0, duration_s: float = 600.0) -> Route:
    return Route(
        route_id=route_id,
        provider=provider,
        summary=f"{provider} route",
        distance_m=distance_m,
        duration_s=duration_s,
        geometry=RouteGeometry(coordinates=coords),
        segments=[],
        limitations=[],
    )


class StubProvider:
    """A routing provider that returns a fixed set of routes."""

    def __init__(self, name: str, routes: List[Route],
                 status: RoutingStatus = RoutingStatus.OK,
                 error_message: Optional[str] = None):
        self._name = name
        self._routes = routes
        self._status = status
        self._error_message = error_message

    @property
    def provider_name(self) -> str:
        return self._name

    def get_routes(self, request: RouteRequest) -> RouteResponse:
        return RouteResponse(
            status=self._status,
            provider=self._name,
            routes=list(self._routes),
            request_id=f"{self._name}-req",
            retrieved_at="2026-10-22T00:00:00+00:00",
            error_message=self._error_message,
        )

    def get_route_geometry(self, route_id: str):
        for route in self._routes:
            if route.route_id == route_id:
                return route.geometry
        return None

    def get_segment_metadata(self, route_id: str):
        return []


class ExplodingProvider:
    """A provider that raises — a failure must not fail the whole request."""

    @property
    def provider_name(self) -> str:
        return "exploding"

    def get_routes(self, request: RouteRequest) -> RouteResponse:
        raise RuntimeError("provider exploded")

    def get_route_geometry(self, route_id: str):
        return None

    def get_segment_metadata(self, route_id: str):
        return []


REQUEST = RouteRequest(origin=Coordinate(12.97, 77.60), destination=Coordinate(12.99, 77.62))


class TestCorridorOverlap(unittest.TestCase):
    def test_identical_corridors_score_one(self):
        coords = _line(0.0)
        self.assertAlmostEqual(corridor_overlap(coords, list(coords)), 1.0, places=6)

    def test_separate_corridors_score_low(self):
        self.assertLess(corridor_overlap(_line(0.0), _line(0.05)), 0.5)

    def test_degenerate_geometry_scores_zero(self):
        self.assertEqual(corridor_overlap([], _line(0.0)), 0.0)


class TestMultiProviderAdapter(unittest.TestCase):
    def test_merges_routes_from_two_providers(self):
        osrm = StubProvider("osrm", [_route("rt-osrm-0", "osrm", _line(0.0))])
        val = StubProvider("valhalla", [_route("rt-val-0", "valhalla", _line(0.05))])
        adapter = MultiProviderRoutingAdapter([osrm, val])

        resp = adapter.get_routes(REQUEST)

        self.assertEqual(resp.status, RoutingStatus.OK)
        self.assertEqual(len(resp.routes), 2)
        self.assertEqual([r.route_id for r in resp.routes], ["rt-osrm-0", "rt-val-0"])
        self.assertEqual(sorted(resp.providers), ["osrm", "valhalla"])

    def test_duplicate_corridor_from_a_second_provider_is_dropped(self):
        """The same road routed by two engines is ONE candidate, not two."""
        osrm = StubProvider("osrm", [_route("rt-osrm-0", "osrm", _line(0.0))])
        val = StubProvider("valhalla", [_route("rt-val-0", "valhalla", _line(0.0005))])
        adapter = MultiProviderRoutingAdapter([osrm, val])

        resp = adapter.get_routes(REQUEST)

        self.assertEqual(len(resp.routes), 1)
        self.assertEqual(resp.routes[0].route_id, "rt-osrm-0")

    def test_single_returned_route_is_never_padded(self):
        """Rule 10: one route stays one route — the cap must not invent more."""
        osrm = StubProvider("osrm", [_route("rt-osrm-0", "osrm", _line(0.0))])
        val = StubProvider("valhalla", [])
        adapter = MultiProviderRoutingAdapter([osrm, val])

        resp = adapter.get_routes(REQUEST)

        self.assertEqual(len(resp.routes), 1)
        self.assertIn("fewer_than_four_routes_returned", resp.limitations)
        self.assertIn("provider_returned_no_routes_valhalla", resp.limitations)

    def test_zero_routes_from_every_provider_is_an_explicit_failure(self):
        osrm = StubProvider("osrm", [])
        val = StubProvider("valhalla", [])
        adapter = MultiProviderRoutingAdapter([osrm, val])

        resp = adapter.get_routes(REQUEST)

        self.assertEqual(resp.status, RoutingStatus.NO_ROUTES_FOUND)
        self.assertEqual(resp.routes, [])
        self.assertIn("zero_routes_returned", resp.limitations)

    def test_one_provider_failure_keeps_the_other_providers_routes(self):
        """Rule 20: a failure is disclosed, and it never removes real routes."""
        osrm = StubProvider("osrm", [_route("rt-osrm-0", "osrm", _line(0.0))])
        adapter = MultiProviderRoutingAdapter([ExplodingProvider(), osrm])

        resp = adapter.get_routes(REQUEST)

        self.assertEqual(resp.status, RoutingStatus.OK)
        self.assertEqual([r.route_id for r in resp.routes], ["rt-osrm-0"])
        self.assertIn("provider_unavailable_exploding", resp.limitations)

    def test_provider_error_status_is_disclosed(self):
        failing = StubProvider(
            "valhalla", [], status=RoutingStatus.PROVIDER_ERROR, error_message="boom")
        osrm = StubProvider("osrm", [_route("rt-osrm-0", "osrm", _line(0.0))])
        adapter = MultiProviderRoutingAdapter([failing, osrm])

        resp = adapter.get_routes(REQUEST)

        self.assertEqual(len(resp.routes), 1)
        self.assertIn("provider_status_valhalla_provider_error", resp.limitations)
        self.assertTrue(any("boom" in limitation for limitation in resp.limitations))

    def test_route_cap_limits_the_composed_list(self):
        providers = [
            StubProvider(f"p{i}", [_route(f"rt-{i}", f"p{i}", _line(0.02 * i))])
            for i in range(6)
        ]
        adapter = MultiProviderRoutingAdapter(providers, max_routes=4)

        resp = adapter.get_routes(REQUEST)

        self.assertEqual(len(resp.routes), 4)

    def test_geometry_lookup_is_dispatched_to_the_owning_provider(self):
        osrm = StubProvider("osrm", [_route("rt-osrm-0", "osrm", _line(0.0))])
        val = StubProvider("valhalla", [_route("rt-val-0", "valhalla", _line(0.05))])
        adapter = MultiProviderRoutingAdapter([osrm, val])
        adapter.get_routes(REQUEST)

        self.assertIsNotNone(adapter.get_route_geometry("rt-val-0"))
        self.assertIsNotNone(adapter.get_route_geometry("rt-osrm-0"))
        self.assertIsNone(adapter.get_route_geometry("rt-missing"))


class TestValhallaPolylineDecoding(unittest.TestCase):
    @staticmethod
    def _encode(coords: List[tuple], precision: int = 6) -> str:
        """Independent reference encoder for Google's polyline format."""
        factor = 10 ** precision
        out: List[str] = []
        prev_lat = prev_lon = 0
        for lon, lat in coords:
            ilat = int(round(lat * factor))
            ilon = int(round(lon * factor))
            for value in (ilat - prev_lat, ilon - prev_lon):
                shifted = ~(value << 1) if value < 0 else (value << 1)
                while shifted >= 0x20:
                    out.append(chr((0x20 | (shifted & 0x1F)) + 63))
                    shifted >>= 5
                out.append(chr(shifted + 63))
            prev_lat, prev_lon = ilat, ilon
        return "".join(out)

    def test_decodes_the_canonical_five_decimal_polyline(self):
        # Google's canonical example: (38.5, -120.2), (40.7, -120.95), (43.252, -126.453)
        encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
        coords = decode_polyline(encoded, precision=5)

        self.assertEqual(len(coords), 3)
        self.assertAlmostEqual(coords[0][0], -120.2, places=5)
        self.assertAlmostEqual(coords[0][1], 38.5, places=5)
        self.assertAlmostEqual(coords[1][0], -120.95, places=5)
        self.assertAlmostEqual(coords[1][1], 40.7, places=5)
        self.assertAlmostEqual(coords[2][0], -126.453, places=5)
        self.assertAlmostEqual(coords[2][1], 43.252, places=5)

    def test_round_trip_at_valhalla_precision(self):
        """Valhalla encodes shapes with 6 decimals; the decoder must match."""
        expected = [
            (77.594600, 12.971600),
            (77.610325, 12.968110),
            (77.628004, 12.974531),
            (77.650000, 12.980000),
        ]
        encoded = self._encode(expected, precision=6)

        coords = decode_polyline(encoded, precision=6)

        self.assertEqual(len(coords), len(expected))
        for (lon, lat), (exp_lon, exp_lat) in zip(coords, expected):
            self.assertAlmostEqual(lon, exp_lon, places=6)
            self.assertAlmostEqual(lat, exp_lat, places=6)

    def test_longitudes_and_latitudes_are_not_swapped(self):
        """A lat/lon swap is the classic polyline bug — pin it down."""
        encoded = self._encode([(77.5946, 12.9716)], precision=6)

        lon, lat = decode_polyline(encoded, precision=6)[0]

        self.assertAlmostEqual(lon, 77.5946, places=6)
        self.assertAlmostEqual(lat, 12.9716, places=6)

    def test_empty_input_decodes_to_no_coordinates(self):
        self.assertEqual(decode_polyline(""), [])

    def test_truncated_input_stops_without_raising(self):
        coords = decode_polyline("_p~iF~ps|U")
        self.assertEqual(len(coords), 1)


if __name__ == "__main__":
    unittest.main()
