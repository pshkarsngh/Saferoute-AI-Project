"""SafeRoute AI — Unit Tests for Facilities Service (PHASE_15).

Governing rules: master_rules.md Rule 11 (facilities separate), Rule 14
(testing honesty), Rule 20 (honest demonstration).
"""

import unittest

from src.facilities.mock_provider import MockFacilitiesProvider
from src.facilities.overpass_provider import OverpassFacilitiesProvider
from src.facilities.schemas import FacilityStatus
from src.facilities.service import (
    FacilitiesService,
    create_facilities_provider,
    load_facilities_config,
)
from src.risk.aggregate import HazardAggregator
from src.risk.engine import DeterministicRiskEngine
from src.risk.schemas import (
    AssessmentStatus,
    CoverageInfo,
    SegmentAssessment,
)

ORIGIN = (12.9716, 77.5946)


class TestFacilitiesService(unittest.TestCase):
    def test_mock_provider_returns_structured_facilities(self):
        prov = MockFacilitiesProvider()
        res = prov.get_nearby_facilities(*ORIGIN, radius_m=2000.0)
        self.assertEqual(res.status, FacilityStatus.OK)
        self.assertGreater(len(res.facilities), 0)
        for f in res.facilities:
            self.assertTrue(f.category)
            self.assertEqual(f.source, "mock_facilities")
            self.assertGreaterEqual(f.distance_m, 0.0)

    def test_zero_facilities_reports_unavailable(self):
        prov = MockFacilitiesProvider()
        res = prov.get_nearby_facilities(*ORIGIN, radius_m=1.0, categories=["hospital"])
        self.assertEqual(res.status, FacilityStatus.UNAVAILABLE)
        self.assertEqual(len(res.facilities), 0)
        self.assertIn("no_facilities_found_within_radius", res.limitations)

    def test_categories_filtering(self):
        prov = MockFacilitiesProvider()
        res = prov.get_nearby_facilities(*ORIGIN, radius_m=3000.0, categories=["fuel"])
        self.assertTrue(all(f.category == "fuel" for f in res.facilities))


    def test_provider_error_statuses_map_explicitly(self):
        cases = {
            "timeout": FacilityStatus.PROVIDER_TIMEOUT,
            "provider_error": FacilityStatus.PROVIDER_ERROR,
            "rate_limited": FacilityStatus.RATE_LIMITED,
        }
        for mode, expected in cases.items():
            res = MockFacilitiesProvider(error_mode=mode).get_nearby_facilities(*ORIGIN)
            self.assertEqual(res.status, expected)
            self.assertEqual(len(res.facilities), 0)
            self.assertIsNotNone(res.error_message)

    def test_overpass_invalid_coordinates_rejected(self):
        prov = OverpassFacilitiesProvider()
        res = prov.get_nearby_facilities(200.0, 77.0)
        self.assertEqual(res.status, FacilityStatus.INVALID_REQUEST)

    def test_factory_creates_expected_providers(self):
        self.assertIsInstance(create_facilities_provider("mock"), MockFacilitiesProvider)
        self.assertIsInstance(create_facilities_provider("overpass"), OverpassFacilitiesProvider)

    def test_provenance_recorded(self):
        res = FacilitiesService().get_nearby_facilities(*ORIGIN, radius_m=2000.0)
        d = res.to_dict()
        for key in ("provider", "retrieved_at", "radius_m", "origin", "categories_requested"):
            self.assertIn(key, d)


class TestFacilitiesSeparationGuardrail(unittest.TestCase):
    """Rule 11: facilities must not change the hazard score or ranking."""

    def _assessment(self):
        seg = SegmentAssessment(
            segment_id="seg-a-0000",
            route_id="route-a",
            model_version="saferoute-yolo11-v1",
            coverage=CoverageInfo(images_total=5, images_used=5, fraction=1.0),
            hazards=[],
            aggregate_hazard=6.0,
            status=AssessmentStatus.ASSESSED,
            limitations=[],
        )
        return seg

    def test_rule_11_score_unchanged_with_and_without_facilities(self):
        engine = DeterministicRiskEngine()
        before = engine.score_route("route-a", [self._assessment()], [400.0])
        # Facilities lookup happens (context only) ...
        FacilitiesService().get_nearby_facilities(*ORIGIN, radius_m=2000.0)
        after = engine.score_route("route-a", [self._assessment()], [400.0])
        self.assertEqual(before.route_score, after.route_score)
        self.assertEqual(before.to_dict(), after.to_dict())

    def test_rule_11_facility_payload_contains_no_score_fields(self):
        d = FacilitiesService().get_nearby_facilities(*ORIGIN).to_dict()
        blob = str(d).lower()
        for banned in ("route_score", "segment_score", "safety_score", "hazard_density", "severity"):
            self.assertNotIn(banned, blob)


if __name__ == "__main__":
    unittest.main()
