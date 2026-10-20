"""SafeRoute AI — Unit Tests for Routing Adapter & Segmentation.

Phase ID: PHASE_13
Follows TRD §10, ARCHITECTURE §8, master_rules.md Rules 8, 10, 13, 14.
"""

import time
import unittest
from pathlib import Path

from src.routing.schemas import (
    Coordinate,
    RouteGeometry,
    RouteRequest,
    RouteResponse,
    RouteSegment,
    RoutingStatus,
)
from src.routing.interfaces import RoutingProvider
from src.routing.segmentation import (
    RouteSegmenter,
    compute_linestring_length_m,
    haversine_distance_m,
)
from src.routing.mock_adapter import MockRoutingAdapter
from src.routing.osrm_adapter import OSRMRoutingAdapter
from src.routing.adapter import create_routing_adapter, load_routing_config

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


class TestRoutingAdapter(unittest.TestCase):
    """Unit test suite for provider-independent routing adapter and segmentation."""

    def setUp(self):
        self.origin = Coordinate(latitude=12.9716, longitude=77.5946)       # Bangalore
        self.destination = Coordinate(latitude=12.9352, longitude=77.6245)  # Koramangala
        self.request = RouteRequest(origin=self.origin, destination=self.destination)
        self.mock_adapter = MockRoutingAdapter(mode="standard_two_routes")

    def test_rule_10_no_route_padding_two_routes(self):
        """Rule 10: When provider returns 2 routes, exactly 2 routes must be emitted (never padded to 4)."""
        self.mock_adapter.set_mode("standard_two_routes")
        response = self.mock_adapter.get_routes(self.request)

        self.assertEqual(response.status, RoutingStatus.OK)
        self.assertEqual(len(response.routes), 2)
        self.assertIn("fewer_than_four_routes_returned", response.limitations)

    def test_rule_10_single_route_not_padded(self):
        """Rule 10: When provider returns 1 route, exactly 1 route must be emitted."""
        self.mock_adapter.set_mode("single_route")
        response = self.mock_adapter.get_routes(self.request)

        self.assertEqual(response.status, RoutingStatus.OK)
        self.assertEqual(len(response.routes), 1)
        self.assertIn("fewer_than_four_routes_returned", response.limitations)

    def test_zero_routes_edge_case(self):
        """When no routes are found, returns NO_ROUTES_FOUND and empty list."""
        self.mock_adapter.set_mode("zero_routes")
        response = self.mock_adapter.get_routes(self.request)

        self.assertEqual(response.status, RoutingStatus.NO_ROUTES_FOUND)
        self.assertEqual(len(response.routes), 0)
        self.assertIn("zero_routes_returned", response.limitations)

    def test_provider_timeout_edge_case(self):
        """Network timeout maps explicitly to PROVIDER_TIMEOUT."""
        self.mock_adapter.set_mode("timeout")
        response = self.mock_adapter.get_routes(self.request)

        self.assertEqual(response.status, RoutingStatus.PROVIDER_TIMEOUT)
        self.assertEqual(len(response.routes), 0)
        self.assertIsNotNone(response.error_message)

    def test_provider_error_edge_case(self):
        """Upstream 5xx error maps explicitly to PROVIDER_ERROR."""
        self.mock_adapter.set_mode("provider_error")
        response = self.mock_adapter.get_routes(self.request)

        self.assertEqual(response.status, RoutingStatus.PROVIDER_ERROR)
        self.assertEqual(len(response.routes), 0)

    def test_rate_limited_edge_case(self):
        """Rate limit HTTP 429 maps explicitly to RATE_LIMITED."""
        self.mock_adapter.set_mode("rate_limited")
        response = self.mock_adapter.get_routes(self.request)

        self.assertEqual(response.status, RoutingStatus.RATE_LIMITED)
        self.assertEqual(len(response.routes), 0)

    def test_stable_segment_identifiers(self):
        """FR-R4 / V5: Segment IDs must be deterministic, stable, and formatted as 'seg-{route_id}-{seq:04d}'."""
        response = self.mock_adapter.get_routes(self.request)
        self.assertGreater(len(response.routes), 0)
        route = response.routes[0]

        self.assertGreater(len(route.segments), 0)
        for idx, seg in enumerate(route.segments):
            expected_id = f"seg-{route.route_id}-{idx:04d}"
            self.assertEqual(seg.segment_id, expected_id)
            self.assertEqual(seg.sequence, idx)
            self.assertGreater(seg.length_m, 0.0)

        # Repeated calls must yield identical IDs
        repeat_resp = self.mock_adapter.get_routes(self.request)
        repeat_route = repeat_resp.routes[0]
        for s1, s2 in zip(route.segments, repeat_route.segments):
            self.assertEqual(s1.segment_id, s2.segment_id)
            self.assertEqual(s1.length_m, s2.length_m)

    def test_haversine_distance_computation(self):
        """Verify Haversine formula against known coordinate pair."""
        # 1 degree of latitude is roughly 111,139 meters
        p1 = (77.0, 12.0)
        p2 = (77.0, 13.0)
        dist = haversine_distance_m(p1, p2)
        self.assertAlmostEqual(dist, 111195.0, delta=500.0)

    def test_segmenter_linestring_subdivision(self):
        """RouteSegmenter cleanly breaks long coordinate lines into target ~200m chunks."""
        segmenter = RouteSegmenter(target_segment_length_m=200.0)
        # Create a line of ~1000m
        coords = [(77.0, 12.0 + i * 0.001) for i in range(10)]
        segments = segmenter.segment_from_coordinates("test_rt", coords)

        self.assertGreater(len(segments), 1)
        total_len = sum(s.length_m for s in segments)
        line_len = compute_linestring_length_m(coords)
        self.assertAlmostEqual(total_len, line_len, delta=1.0)

    def test_interface_compliance_and_metadata_retrieval(self):
        """V2: Adapter adheres to RoutingProvider protocol methods."""
        self.assertTrue(issubclass(MockRoutingAdapter, RoutingProvider))
        self.assertTrue(issubclass(OSRMRoutingAdapter, RoutingProvider))

        response = self.mock_adapter.get_routes(self.request)
        r_id = response.routes[0].route_id

        # Query geometry and segments via protocol methods
        geom = self.mock_adapter.get_route_geometry(r_id)
        self.assertIsNotNone(geom)
        self.assertEqual(geom.type, "LineString")
        self.assertGreater(len(geom.coordinates), 0)

        segs = self.mock_adapter.get_segment_metadata(r_id)
        self.assertEqual(len(segs), len(response.routes[0].segments))

    def test_rule_8_imagery_guardrail_in_config(self):
        """Rule 8: Configuration explicitly forbids assuming routing API grants imagery rights."""
        cfg = load_routing_config()
        self.assertIn("guardrails", cfg)
        self.assertFalse(cfg["guardrails"].get("imagery_rights_granted", True))

    def test_factory_creation(self):
        """Factory creates correct provider instances based on type."""
        mock_prov = create_routing_adapter("mock")
        self.assertIsInstance(mock_prov, MockRoutingAdapter)
        self.assertEqual(mock_prov.provider_name, "mock_routing")

        osrm_prov = create_routing_adapter("osrm")
        self.assertIsInstance(osrm_prov, OSRMRoutingAdapter)
        self.assertEqual(osrm_prov.provider_name, "osrm")

    def test_serialization_contracts(self):
        """Response and route objects serialize cleanly to JSON-compatible dictionaries."""
        response = self.mock_adapter.get_routes(self.request)
        d = response.to_dict()

        self.assertIn("status", d)
        self.assertIn("provider", d)
        self.assertIn("routes", d)
        self.assertIn("limitations", d)
        self.assertIn("retrieved_at", d)

        first_route = d["routes"][0]
        self.assertIn("route_id", first_route)
        self.assertIn("distance_m", first_route)
        self.assertIn("duration_s", first_route)
        self.assertIn("geometry", first_route)
        self.assertIn("segments", first_route)


class TestOSRMResponseCache(unittest.TestCase):
    """PHASE_27: identical OSRM queries within the TTL are not refetched.

    The UI requests the same coordinates twice (fast geometry preview, then the
    full assessment), so the adapter reuses one provider response. Nothing is
    fabricated: only successful responses are cached, and a different query or
    an expired entry always hits the provider again (Rules 9, 10).
    """

    def setUp(self):
        self.adapter = OSRMRoutingAdapter()
        self.origin = Coordinate(latitude=12.9716, longitude=77.5946)
        self.destination = Coordinate(latitude=12.9352, longitude=77.6245)
        self.request = RouteRequest(origin=self.origin, destination=self.destination)
        self.fetch_calls = []

    def _patch_fetch(self, adapter, payload, status=RoutingStatus.OK):
        """Replace the network call with a recorder returning a canned payload."""

        def fake_fetch(url):
            self.fetch_calls.append(url)
            return payload, status, None

        adapter._fetch_with_retry = fake_fetch  # type: ignore[assignment]
        return adapter

    @staticmethod
    def _payload():
        return {
            "code": "Ok",
            "routes": [
                {
                    "distance": 1000.0,
                    "duration": 100.0,
                    "geometry": {"coordinates": [[77.60, 12.97], [77.61, 12.98]]},
                    "legs": [
                        {
                            "steps": [
                                {
                                    "name": "Test Road",
                                    "distance": 1000.0,
                                    "duration": 100.0,
                                    "geometry": {
                                        "type": "LineString",
                                        "coordinates": [[77.60, 12.97], [77.61, 12.98]],
                                    },
                                }
                            ]
                        }
                    ],
                }
            ],
        }

    def test_identical_query_is_cached(self):
        self._patch_fetch(self.adapter, self._payload())
        first = self.adapter.get_routes(self.request)
        second = self.adapter.get_routes(self.request)

        self.assertEqual(first.status, RoutingStatus.OK)
        self.assertEqual(len(self.fetch_calls), 1, "second identical query must reuse the cache")
        self.assertEqual(
            [r.route_id for r in first.routes], [r.route_id for r in second.routes]
        )

    def test_different_coordinates_refetch(self):
        self._patch_fetch(self.adapter, self._payload())
        self.adapter.get_routes(self.request)
        other = RouteRequest(
            origin=self.origin,
            destination=Coordinate(latitude=12.9000, longitude=77.7000),
        )
        self.adapter.get_routes(other)
        self.assertEqual(len(self.fetch_calls), 2)

    def test_expired_entry_refetches(self):
        self._patch_fetch(self.adapter, self._payload())
        self.adapter.get_routes(self.request)
        # Force the cached entry to look older than the TTL.
        key = self.adapter._response_cache_key(self.request)
        _, response = self.adapter._response_cache[key]
        self.adapter._response_cache[key] = (
            time.monotonic() - self.adapter.ROUTE_CACHE_TTL_SECONDS - 1.0,
            response,
        )
        self.adapter.get_routes(self.request)
        self.assertEqual(len(self.fetch_calls), 2)

    def test_failed_query_is_not_cached(self):
        self._patch_fetch(self.adapter, None, status=RoutingStatus.PROVIDER_TIMEOUT)
        first = self.adapter.get_routes(self.request)
        second = self.adapter.get_routes(self.request)

        self.assertEqual(first.status, RoutingStatus.PROVIDER_TIMEOUT)
        self.assertEqual(
            len(self.fetch_calls), 2,
            "a provider outage must not be masked by a cached failure",
        )

    def test_cache_evicts_beyond_max_entries(self):
        self._patch_fetch(self.adapter, self._payload())
        self.adapter.ROUTE_CACHE_MAX_ENTRIES = 2
        for i in range(4):
            req = RouteRequest(
                origin=self.origin,
                destination=Coordinate(latitude=12.90 + i * 0.01, longitude=77.70),
            )
            self.adapter.get_routes(req)
        self.assertLessEqual(len(self.adapter._response_cache), 2)


if __name__ == "__main__":
    unittest.main()
