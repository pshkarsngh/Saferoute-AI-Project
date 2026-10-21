"""SafeRoute AI — API-level tests for `POST /api/facilities` (PHASE_29).

The backend endpoint is the single source of truth for facility data, so the
tests cover both request shapes (point and route corridor) and the honest
status handling the browser depends on (Rules 11, 14, 20).
"""

import unittest
from pathlib import Path

from src.api.app import SafeRouteAPI
from src.api.pipeline import SafetyAnalysisPipeline
from src.api.store import AnalysisStore
from src.facilities.schemas import (
    DISTANCE_STRAIGHT_LINE,
    Facility,
    FacilityResult,
    FacilityStatus,
)
from src.facilities.service import FacilitiesService
from src.geocoding.mock_geocoder import MockGeocoder

ROUTE = [
    [77.5946, 12.9716],
    [77.5960, 12.9730],
    [77.5980, 12.9750],
]


class StubProvider:
    """Facilities provider double with a configurable outcome."""

    def __init__(self, status=FacilityStatus.OK, facilities=None, error_message=None):
        self.status = status
        self.facilities = list(facilities or [])
        self.error_message = error_message
        self.bbox_calls = []

    @property
    def provider_name(self) -> str:
        return "overpass"

    def _result(self):
        return FacilityResult(
            status=self.status,
            provider=self.provider_name,
            facilities=list(self.facilities),
            categories_requested=["hospital"],
            radius_m=1000.0,
            origin_latitude=12.9716,
            origin_longitude=77.5946,
            retrieved_at="2026-10-21T00:00:00+00:00",
            error_message=self.error_message,
        )

    def get_nearby_facilities(self, latitude, longitude, radius_m=None, categories=None):
        return self._result()

    def get_facilities_in_bbox(self, bbox, categories=None):
        self.bbox_calls.append((bbox, categories))
        return self._result()


def _hospital():
    return Facility(
        facility_id="osm-node-99",
        category="hospital",
        subtype="hospital",
        name="City General Hospital",
        latitude=12.9725,
        longitude=77.5955,
        distance_m=120.0,
        distance_kind=DISTANCE_STRAIGHT_LINE,
        source="overpass",
        osm_tags={"amenity": "hospital", "emergency": "yes"},
        attributes_verified=False,
    )


class TestFacilitiesApi(unittest.TestCase):
    def setUp(self):
        self.db = Path("data/test_facilities_api.db")
        if self.db.exists():
            self.db.unlink()
        self.store = AnalysisStore(db_path=self.db)
        self.provider = StubProvider(facilities=[_hospital()])
        self.pipeline = SafetyAnalysisPipeline(
            facilities_service=FacilitiesService(provider=self.provider))
        self.api = SafeRouteAPI(pipeline=self.pipeline, store=self.store, geocoder=MockGeocoder())

    def tearDown(self):
        if self.db.exists():
            self.db.unlink()

    # ------------------------------------------------------------------ #
    # Route-corridor request shape (the one the SafeRoute UI uses)
    # ------------------------------------------------------------------ #
    def test_corridor_request_returns_facilities_with_provenance(self):
        code, obj = self.api.facilities({
            "route": {"polylines": [ROUTE]},
            "radius_m": 1000,
            "categories": ["hospital", "medical"],
        })
        self.assertEqual(code, 200)
        self.assertEqual(obj["status"], "ok")
        self.assertEqual(obj["facilities_count"], 1)
        self.assertEqual(obj["distance_basis"], DISTANCE_STRAIGHT_LINE)
        self.assertTrue(obj["source_attribution"])
        self.assertTrue(obj["retrieved_at"])
        self.assertIn("not independently verified", obj["attributes_note"])
        self.assertEqual(len(self.provider.bbox_calls), 1)

    def test_corridor_request_marks_attributes_unverified(self):
        _, obj = self.api.facilities({"route": {"polylines": [ROUTE]}})
        facility = obj["facilities"][0]
        self.assertFalse(facility["attributes_verified"])
        self.assertEqual(facility["osm_tags"]["emergency"], "yes")

    def test_corridor_request_reports_no_road_travel_time_without_a_real_router(self):
        """The default pipeline router is the mock one: no road figure is shown."""
        _, obj = self.api.facilities({"route": {"polylines": [ROUTE]}})
        self.assertFalse(obj["road_access_available"])
        self.assertIn("unavailable", obj["road_access_note"].lower())
        for facility in obj["facilities"]:
            self.assertIsNone(facility["road_travel_time_s"])
            self.assertIsNone(facility["road_distance_m"])

    def test_corridor_request_can_opt_out_of_road_access(self):
        _, obj = self.api.facilities({
            "route": {"polylines": [ROUTE]},
            "include_road_access": False,
        })
        self.assertFalse(obj["road_access_available"])

    def test_corridor_request_without_geometry_is_reported_honestly(self):
        code, obj = self.api.facilities({"route": {"polylines": []}})
        self.assertEqual(code, 200)
        self.assertEqual(obj["status"], "invalid_request")
        self.assertEqual(obj["facilities_count"], 0)
        self.assertIn("no_route_geometry_supplied", obj["limitations"])

    def test_provider_error_is_returned_as_a_provider_error(self):
        self.provider.status = FacilityStatus.PROVIDER_ERROR
        self.provider.error_message = "The facility data provider returned an error."
        code, obj = self.api.facilities({"route": {"polylines": [ROUTE]}})
        self.assertEqual(code, 200)
        self.assertEqual(obj["status"], "provider_error")
        self.assertNotEqual(obj["status"], "unavailable")
        self.assertEqual(obj["facilities_count"], 0)
        self.assertIsNotNone(obj["error_message"])

    def test_provider_timeout_is_returned_as_a_provider_timeout(self):
        self.provider.status = FacilityStatus.PROVIDER_TIMEOUT
        self.provider.error_message = "The facility data provider did not respond in time."
        _, obj = self.api.facilities({"route": {"polylines": [ROUTE]}})
        self.assertEqual(obj["status"], "provider_timeout")
        self.assertEqual(obj["facilities_count"], 0)

    def test_rate_limited_is_not_reported_as_an_empty_area(self):
        self.provider.status = FacilityStatus.RATE_LIMITED
        self.provider.error_message = "The facility data provider rate-limited the request."
        _, obj = self.api.facilities({"route": {"polylines": [ROUTE]}})
        self.assertEqual(obj["status"], "rate_limited")
        self.assertEqual(obj["facilities_count"], 0)

    # ------------------------------------------------------------------ #
    # Legacy point request shape
    # ------------------------------------------------------------------ #
    def test_point_request_still_works(self):
        code, obj = self.api.facilities({
            "location": {"latitude": 12.9716, "longitude": 77.5946},
            "radius_m": 1000,
        })
        self.assertEqual(code, 200)
        self.assertEqual(obj["status"], "ok")
        self.assertEqual(obj["facilities_count"], 1)
        self.assertEqual(len(self.provider.bbox_calls), 0)

    def test_point_request_without_a_location_is_rejected(self):
        code, obj = self.api.facilities({})
        self.assertEqual(code, 400)
        self.assertEqual(obj["status"], "failed")

    def test_unusable_radius_falls_back_to_the_default(self):
        code, obj = self.api.facilities({
            "route": {"polylines": [ROUTE]},
            "radius_m": "not-a-number",
        })
        self.assertEqual(code, 200)
        self.assertGreater(obj["radius_m"], 0)

    # ------------------------------------------------------------------ #
    # Rule 11 — the endpoint must not leak into the risk scoring
    # ------------------------------------------------------------------ #
    def test_facilities_endpoint_response_contains_no_score_fields(self):
        _, obj = self.api.facilities({"route": {"polylines": [ROUTE]}})
        blob = str(obj).lower()
        for banned in ("route_score", "segment_score", "safety_score", "hazard_density", "severity"):
            self.assertNotIn(banned, blob)


if __name__ == "__main__":
    unittest.main()
