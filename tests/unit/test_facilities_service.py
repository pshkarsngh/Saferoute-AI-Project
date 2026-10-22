"""SafeRoute AI — Unit Tests for Facilities Service (PHASE_15, PHASE_29).

Governing rules: master_rules.md Rule 11 (facilities separate), Rule 14
(testing honesty), Rule 17 (provenance), Rule 20 (honest demonstration).

PHASE_29 covers the consolidated lookup: the backend is the single source of
truth for facility data, distances state how they were measured, a road travel
time exists only when a real routing provider returned one, and a provider
failure is never turned into "no hospitals exist".
"""

import unittest
from unittest import mock

from src.facilities.interfaces import FacilitiesProvider
from src.facilities.mock_provider import MockFacilitiesProvider
from src.facilities.overpass_provider import OverpassFacilitiesProvider
from src.facilities.schemas import (
    DISTANCE_STRAIGHT_LINE,
    Facility,
    FacilityResult,
    FacilityStatus,
)
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
from src.routing.schemas import (
    Coordinate,
    Route,
    RouteGeometry,
    RouteRequest,
    RouteResponse,
    RoutingStatus,
)

ORIGIN = (12.9716, 77.5946)

#: A short route through Bangalore, as [[lon, lat], ...].
ROUTE = [
    [77.5946, 12.9716],
    [77.5960, 12.9730],
    [77.5980, 12.9750],
]


def _facility(category="hospital", subtype="hospital", lat=12.9722, lon=77.5955,
              distance_m=120.0, tags=None, facility_id="osm-node-1") -> Facility:
    return Facility(
        facility_id=facility_id,
        category=category,
        subtype=subtype,
        name="Test Hospital",
        latitude=lat,
        longitude=lon,
        distance_m=distance_m,
        distance_kind=DISTANCE_STRAIGHT_LINE,
        source="overpass",
        osm_tags=dict(tags or {}),
        attributes_verified=False,
    )


class StubProvider(FacilitiesProvider):
    """Provider double with a configurable outcome."""

    def __init__(self, status=FacilityStatus.OK, facilities=None, error_message=None):
        self.status = status
        self.facilities = list(facilities or [])
        self.error_message = error_message
        self.bbox_calls = []
        self.point_calls = []

    @property
    def provider_name(self) -> str:
        return "overpass"

    def _result(self, facilities=None):
        return FacilityResult(
            status=self.status,
            provider=self.provider_name,
            facilities=list(self.facilities if facilities is None else facilities),
            categories_requested=["hospital"],
            radius_m=1000.0,
            origin_latitude=ORIGIN[0],
            origin_longitude=ORIGIN[1],
            retrieved_at="2026-10-21T00:00:00+00:00",
            error_message=self.error_message,
        )

    def get_nearby_facilities(self, latitude, longitude, radius_m=None, categories=None):
        self.point_calls.append((latitude, longitude, radius_m, categories))
        return self._result()

    def get_facilities_in_bbox(self, bbox, categories=None):
        self.bbox_calls.append((bbox, categories))
        return self._result()


class StubRoutingProvider:
    """Routing double emulating the OSRM response shape."""

    provider_name = "osrm"

    def __init__(self, status=RoutingStatus.OK, routes=None, error_message=None):
        self.status = status
        self.routes = routes if routes is not None else [
            Route(
                route_id="r-1",
                provider="osrm",
                summary="stub",
                distance_m=1450.0,
                duration_s=210.0,
                geometry=RouteGeometry(coordinates=[(77.5955, 12.9725)]),
            )
        ]
        self.error_message = error_message
        self.requests = []

    def get_routes(self, request: RouteRequest) -> RouteResponse:
        self.requests.append(request)
        return RouteResponse(
            status=self.status,
            provider=self.provider_name,
            routes=list(self.routes),
            request_id="req-1",
            retrieved_at="2026-10-21T00:00:00+00:00",
            error_message=self.error_message,
        )


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


class TestFacilitiesCorridorLookup(unittest.TestCase):
    """PHASE_29 — the route-corridor lookup used by the SafeRoute UI."""

    def test_corridor_returns_facilities_measured_against_the_route(self):
        prov = StubProvider(facilities=[_facility()])
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=1000, include_road_access=False)
        self.assertEqual(res.status, FacilityStatus.OK)
        self.assertEqual(len(res.facilities), 1)
        facility = res.facilities[0]
        self.assertEqual(facility.distance_kind, DISTANCE_STRAIGHT_LINE)
        self.assertGreater(facility.distance_m, 0.0)
        self.assertIsNone(facility.road_travel_time_s)
        self.assertIsNone(facility.road_distance_m)
        self.assertEqual(res.distance_basis, DISTANCE_STRAIGHT_LINE)

    def test_corridor_excludes_facilities_outside_the_radius(self):
        far = _facility(lat=12.9800, lon=77.6100, distance_m=9000.0)
        prov = StubProvider(facilities=[far])
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=500, include_road_access=False)
        self.assertEqual(res.status, FacilityStatus.UNAVAILABLE)
        self.assertEqual(len(res.facilities), 0)

    def test_corridor_without_geometry_is_an_invalid_request(self):
        prov = StubProvider(facilities=[_facility()])
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([], radius_m=1000, include_road_access=False)
        self.assertEqual(res.status, FacilityStatus.INVALID_REQUEST)
        self.assertEqual(len(res.facilities), 0)
        self.assertIn("no_route_geometry_supplied", res.limitations)
        self.assertIsNotNone(res.error_message)

    def test_provider_error_is_never_reported_as_no_facilities(self):
        """Rule 20: a provider failure must not become "no hospitals exist"."""
        prov = StubProvider(status=FacilityStatus.PROVIDER_ERROR,
                            error_message="The facility data provider returned an error.")
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=1000, include_road_access=False)
        self.assertEqual(res.status, FacilityStatus.PROVIDER_ERROR)
        self.assertNotEqual(res.status, FacilityStatus.UNAVAILABLE)
        self.assertEqual(len(res.facilities), 0)
        self.assertIsNotNone(res.error_message)

    def test_provider_timeout_and_rate_limit_keep_their_own_status(self):
        for provider_status in (FacilityStatus.PROVIDER_TIMEOUT, FacilityStatus.RATE_LIMITED):
            prov = StubProvider(status=provider_status, error_message="provider said no")
            svc = FacilitiesService(provider=prov)
            res = svc.get_facilities_near_route([ROUTE], radius_m=1000, include_road_access=False)
            self.assertEqual(res.status, provider_status)
            self.assertEqual(len(res.facilities), 0)

    def test_empty_result_is_unavailable_with_an_explicit_caveat(self):
        prov = StubProvider(status=FacilityStatus.UNAVAILABLE, facilities=[])
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=1000, include_road_access=False)
        self.assertEqual(res.status, FacilityStatus.UNAVAILABLE)
        joined = " ".join(res.notes).lower()
        self.assertIn("not proof", joined)

    def test_provenance_recorded_for_corridor_lookup(self):
        prov = StubProvider(facilities=[_facility()])
        svc = FacilitiesService(provider=prov)
        d = svc.get_facilities_near_route([ROUTE], radius_m=1000, include_road_access=False).to_dict()
        for key in ("provider", "retrieved_at", "radius_m", "origin", "categories_requested",
                    "source_attribution", "attributes_note", "distance_basis", "limitations"):
            self.assertIn(key, d)
        self.assertTrue(d["source_attribution"])

    def test_osm_attributes_are_carried_verbatim_and_flagged_unverified(self):
        prov = StubProvider(facilities=[_facility(tags={
            "amenity": "hospital", "emergency": "yes", "opening_hours": "24/7",
        })])
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=1000, include_road_access=False)
        facility = res.facilities[0]
        self.assertEqual(facility.osm_tags["emergency"], "yes")
        self.assertFalse(facility.attributes_verified)
        d = res.to_dict()
        self.assertFalse(d["facilities"][0]["attributes_verified"])
        self.assertIn("not independently verified", d["attributes_note"])


class TestFacilitiesRoadAccess(unittest.TestCase):
    """PHASE_29 — road travel time only ever comes from a real routing request."""

    def test_road_travel_time_attached_from_a_real_routing_provider(self):
        prov = StubProvider(facilities=[_facility()])
        routing = StubRoutingProvider()
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=1000, routing_provider=routing)
        facility = res.facilities[0]
        self.assertIsNotNone(facility.road_travel_time_s)
        self.assertIsNotNone(facility.road_distance_m)
        self.assertEqual(facility.road_access_source, "osrm")
        self.assertTrue(res.road_access_available)
        self.assertEqual(len(routing.requests), 1)

    def test_straight_line_and_road_distance_are_both_labelled(self):
        prov = StubProvider(facilities=[_facility(distance_m=120.0)])
        routing = StubRoutingProvider()
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=1000, routing_provider=routing)
        facility = res.facilities[0]
        self.assertEqual(facility.distance_kind, DISTANCE_STRAIGHT_LINE)
        self.assertNotEqual(facility.distance_m, facility.road_distance_m)

    def test_synthetic_routing_provider_never_produces_a_road_travel_time(self):
        synthetic = StubRoutingProvider()
        synthetic.provider_name = "mock_routing"
        prov = StubProvider(facilities=[_facility()])
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=1000, routing_provider=synthetic)
        facility = res.facilities[0]
        self.assertIsNone(facility.road_travel_time_s)
        self.assertIsNone(facility.road_distance_m)
        self.assertFalse(res.road_access_available)
        self.assertIn("synthetic", res.road_access_note.lower())
        self.assertEqual(len(synthetic.requests), 0)

    def test_failed_routing_request_leaves_road_travel_time_unavailable(self):
        failing = StubRoutingProvider(status=RoutingStatus.NO_ROUTES_FOUND, routes=[],
                                      error_message="no route")
        prov = StubProvider(facilities=[_facility()])
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=1000, routing_provider=failing)
        facility = res.facilities[0]
        self.assertIsNone(facility.road_travel_time_s)
        self.assertIsNone(facility.road_distance_m)
        self.assertFalse(res.road_access_available)
        self.assertIn("unavailable", res.road_access_note.lower())

    def test_no_routing_provider_leaves_road_travel_time_unavailable(self):
        prov = StubProvider(facilities=[_facility()])
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=1000, routing_provider=None)
        self.assertFalse(res.road_access_available)
        self.assertIsNone(res.facilities[0].road_travel_time_s)
        self.assertIn("unavailable", res.road_access_note.lower())

    def test_road_access_is_bounded_to_the_nearest_facility_per_category(self):
        near = _facility(category="hospital", subtype="hospital", lat=12.9717, lon=77.5947,
                         distance_m=30.0, facility_id="osm-node-near")
        far = _facility(category="hospital", subtype="hospital", lat=12.9800, lon=77.6000,
                        distance_m=250.0, facility_id="osm-node-far")
        other = _facility(category="medical", subtype="clinic", lat=12.9719, lon=77.5950,
                          distance_m=60.0, facility_id="osm-node-clinic")
        prov = StubProvider(facilities=[near, far, other])
        routing = StubRoutingProvider()
        svc = FacilitiesService(provider=prov)
        res = svc.get_facilities_near_route([ROUTE], radius_m=1000, routing_provider=routing)
        self.assertEqual(len(routing.requests), 2)  # one per category
        with_road = [f for f in res.facilities if f.road_travel_time_s is not None]
        self.assertEqual(len(with_road), 2)
        # Only the NEAREST hospital of the category gets a road figure.
        hospital_with_road = [f for f in with_road if f.category == "hospital"]
        self.assertEqual(len(hospital_with_road), 1)
        self.assertEqual(hospital_with_road[0].facility_id, near.facility_id)


class TestOverpassProviderBehaviour(unittest.TestCase):
    """PHASE_29 — provider-level behaviour: parsing, failover, honest statuses."""

    def _provider(self, **kwargs):
        return OverpassFacilitiesProvider(
            base_url="https://primary.example/api/interpreter",
            timeout_seconds=0.05,
            max_retries=0,
            backoff_factor_seconds=0.0,
            query_gap_seconds=0.0,
            query_deadline_seconds=5.0,
            base_urls=[
                "https://primary.example/api/interpreter",
                "https://mirror.example/api/interpreter",
            ],
            max_endpoints=2,
            **kwargs,
        )

    def test_query_lists_every_selector_of_the_category(self):
        prov = OverpassFacilitiesProvider()
        query = prov._category_query("medical", "around:1000,12.9,77.5")
        self.assertIn('node["amenity"="pharmacy"]', query)
        self.assertIn('node["amenity"="clinic"]', query)
        self.assertIn('way["amenity"="dentist"]', query)

    def test_tags_are_parsed_into_category_subtype_and_raw_attributes(self):
        prov = OverpassFacilitiesProvider()
        elements = [{
            "type": "node", "id": 42, "lat": 12.9725, "lon": 77.5955,
            "tags": {"amenity": "hospital", "name": "City Hospital",
                     "emergency": "yes", "opening_hours": "24/7"},
        }]
        facilities = prov._to_facilities(elements, ["hospital"], (77.5946, 12.9716))
        self.assertEqual(len(facilities), 1)
        facility = facilities[0]
        self.assertEqual(facility.category, "hospital")
        self.assertEqual(facility.subtype, "hospital")
        self.assertEqual(facility.name, "City Hospital")
        self.assertEqual(facility.osm_tags["emergency"], "yes")
        self.assertFalse(facility.attributes_verified)

    def test_granular_subtype_is_reported_for_medical_categories(self):
        prov = OverpassFacilitiesProvider()
        elements = [{
            "type": "node", "id": 7, "lat": 12.9725, "lon": 77.5955,
            "tags": {"amenity": "clinic", "name": "Neighbourhood Clinic"},
        }]
        facilities = prov._to_facilities(elements, ["medical"], (77.5946, 12.9716))
        self.assertEqual(facilities[0].category, "medical")
        self.assertEqual(facilities[0].subtype, "clinic")

    def test_provider_fails_over_to_the_next_mirror(self):
        prov = self._provider()
        payload = {"elements": [{"type": "node", "id": 1, "lat": 12.9725, "lon": 77.5955,
                                 "tags": {"amenity": "hospital", "name": "H"}}]}
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req.full_url)
            if "primary.example" in req.full_url:
                raise OSError("primary mirror is down")
            body = __import__("json").dumps(payload).encode()
            response = mock.MagicMock()
            response.read.return_value = body
            response.__enter__.return_value = response
            response.__exit__.return_value = False
            return response

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = prov.get_facilities_in_bbox((12.96, 77.58, 12.98, 77.61), ["hospital"])

        self.assertEqual(result.status, FacilityStatus.OK)
        self.assertEqual(len(result.facilities), 1)
        self.assertEqual(len(calls), 2)
        self.assertIn("mirror.example", calls[1])

    def test_http_429_maps_to_rate_limited(self):
        import urllib.error

        prov = self._provider()

        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = prov.get_facilities_in_bbox((12.96, 77.58, 12.98, 77.61), ["hospital"])
        self.assertEqual(result.status, FacilityStatus.RATE_LIMITED)
        self.assertEqual(len(result.facilities), 0)

    def test_timeout_maps_to_provider_timeout(self):
        import socket

        prov = self._provider()

        def fake_urlopen(req, timeout=None):
            raise socket.timeout("timed out")

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = prov.get_facilities_in_bbox((12.96, 77.58, 12.98, 77.61), ["hospital"])
        self.assertEqual(result.status, FacilityStatus.PROVIDER_TIMEOUT)
        self.assertEqual(len(result.facilities), 0)

    def test_deadline_stops_the_lookup_and_is_disclosed(self):
        import socket
        import time

        prov = OverpassFacilitiesProvider(
            base_url="https://primary.example/api/interpreter",
            timeout_seconds=0.05,
            max_retries=1,
            backoff_factor_seconds=0.0,
            query_gap_seconds=0.0,
            query_deadline_seconds=0.05,
            base_urls=["https://primary.example/api/interpreter"],
            max_endpoints=1,
        )

        def fake_urlopen(req, timeout=None):
            time.sleep(0.15)  # the request outlives the whole lookup budget
            raise socket.timeout("timed out")

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = prov.get_facilities_in_bbox((12.96, 77.58, 12.98, 77.61), ["hospital"])
        self.assertEqual(result.status, FacilityStatus.PROVIDER_ERROR)
        self.assertEqual(len(result.facilities), 0)
        self.assertTrue(any("budget" in lim for lim in result.limitations))

    def test_empty_overpass_response_is_unavailable_not_an_empty_claim(self):
        import json

        prov = self._provider()

        def fake_urlopen(req, timeout=None):
            response = mock.MagicMock()
            response.read.return_value = json.dumps({"elements": []}).encode()
            response.__enter__.return_value = response
            response.__exit__.return_value = False
            return response

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = prov.get_facilities_in_bbox((12.96, 77.58, 12.98, 77.61), ["hospital"])
        self.assertEqual(result.status, FacilityStatus.UNAVAILABLE)
        self.assertIn("no_facilities_found_within_radius", result.limitations)


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

    def test_rule_11_score_identical_when_facilities_present_missing_or_unavailable(self):
        """The corridor lookup outcome must never influence the hazard score."""
        engine = DeterministicRiskEngine()
        reference = engine.score_route("route-a", [self._assessment()], [400.0]).to_dict()

        cases = {
            "present": StubProvider(facilities=[_facility()]),
            "missing": StubProvider(status=FacilityStatus.UNAVAILABLE, facilities=[]),
            "unavailable": StubProvider(status=FacilityStatus.PROVIDER_ERROR,
                                       error_message="provider down"),
        }
        for label, provider in cases.items():
            svc = FacilitiesService(provider=provider)
            svc.get_facilities_near_route([ROUTE], radius_m=1000, include_road_access=False)
            scored = engine.score_route("route-a", [self._assessment()], [400.0]).to_dict()
            self.assertEqual(scored, reference, f"score changed with facilities '{label}'")

    def test_rule_11_corridor_payload_contains_no_score_fields(self):
        prov = StubProvider(facilities=[_facility()])
        svc = FacilitiesService(provider=prov)
        blob = str(svc.get_facilities_near_route([ROUTE], radius_m=1000,
                                                  include_road_access=False).to_dict()).lower()
        for banned in ("route_score", "segment_score", "safety_score", "hazard_density", "severity"):
            self.assertNotIn(banned, blob)


class TestFacilitiesConfiguration(unittest.TestCase):
    """PHASE_29 — configuration guards."""

    def test_config_declares_the_guardrail(self):
        cfg = load_facilities_config()
        self.assertFalse(cfg["guardrails"]["facilities_in_hazard_score"])

    def test_config_declares_road_access_bounds(self):
        cfg = load_facilities_config()
        road = cfg["road_access"]
        self.assertIn("max_per_category", road)
        self.assertIn("max_requests", road)
        self.assertGreaterEqual(int(road["max_requests"]), 1)

    def test_factory_reads_the_mirror_list_from_the_config(self):
        provider = create_facilities_provider("overpass")
        self.assertGreaterEqual(len(provider.base_urls), 2)
        self.assertEqual(provider.base_urls[0], provider.base_url)


class TestFacilitiesPerRouteLookup(unittest.TestCase):
    """PHASE_32 — each route is measured against its OWN geometry."""

    ROUTE_A = [[77.5946, 12.9716], [77.5950, 12.9717]]
    ROUTE_B = [[77.5970, 12.9718], [77.5975, 12.9720]]

    def test_each_route_receives_only_its_own_nearby_facilities(self):
        near_a = _facility(lat=12.9717, lon=77.5947, facility_id="a-1")
        near_b = _facility(lat=12.9720, lon=77.5975, facility_id="b-1")
        prov = StubProvider(facilities=[near_a, near_b])
        svc = FacilitiesService(provider=prov)

        body = svc.get_facilities_for_routes(
            [
                {"route_id": "route-a", "polylines": [self.ROUTE_A]},
                {"route_id": "route-b", "polylines": [self.ROUTE_B]},
            ],
            radius_m=100,
            include_road_access=False,
        )

        self.assertEqual(body["status"], "ok")
        self.assertEqual(set(body["routes"]), {"route-a", "route-b"})
        route_a = body["routes"]["route-a"]
        route_b = body["routes"]["route-b"]
        self.assertEqual([f["facility_id"] for f in route_a["facilities"]], ["a-1"])
        self.assertEqual([f["facility_id"] for f in route_b["facilities"]], ["b-1"])
        self.assertLess(route_a["facilities"][0]["distance_m"], 100)
        self.assertLess(route_b["facilities"][0]["distance_m"], 100)
        self.assertNotEqual(
            route_a["facilities"][0]["distance_m"],
            route_b["facilities"][0]["distance_m"],
        )

    def test_one_provider_query_serves_every_route(self):
        prov = StubProvider(facilities=[_facility()])
        svc = FacilitiesService(provider=prov)
        svc.get_facilities_for_routes(
            [{"route_id": f"r{i}", "polylines": [self.ROUTE_A]} for i in range(3)],
            radius_m=1000,
            include_road_access=False,
        )
        self.assertEqual(len(prov.bbox_calls), 1)

    def test_route_without_geometry_does_not_poison_the_other_routes(self):
        prov = StubProvider(facilities=[_facility(lat=12.9717, lon=77.5947)])
        svc = FacilitiesService(provider=prov)
        body = svc.get_facilities_for_routes(
            [
                {"route_id": "ok", "polylines": [self.ROUTE_A]},
                {"route_id": "empty", "polylines": []},
            ],
            radius_m=100,
            include_road_access=False,
        )
        self.assertEqual(body["routes"]["ok"]["status"], "ok")
        self.assertEqual(body["routes"]["empty"]["status"], "invalid_request")
        self.assertIn(
            "no_route_geometry_supplied",
            body["routes"]["empty"]["limitations"],
        )

    def test_empty_route_list_is_rejected_honestly(self):
        svc = FacilitiesService(provider=StubProvider(facilities=[]))
        body = svc.get_facilities_for_routes([], radius_m=1000, include_road_access=False)
        self.assertEqual(body["status"], "invalid_request")
        self.assertEqual(body["routes"], {})
        self.assertIn("no_routes_supplied", body["limitations"])

    def test_provider_failure_keeps_its_status_for_every_route(self):
        prov = StubProvider(
            status=FacilityStatus.PROVIDER_ERROR,
            error_message="provider down",
        )
        svc = FacilitiesService(provider=prov)
        body = svc.get_facilities_for_routes(
            [{"route_id": f"r{i}", "polylines": [self.ROUTE_A]} for i in range(2)],
            radius_m=1000,
            include_road_access=False,
        )
        self.assertEqual(body["status"], "provider_error")
        for route in body["routes"].values():
            self.assertEqual(route["status"], "provider_error")
            self.assertNotEqual(route["status"], "unavailable")
            self.assertEqual(route["facilities_count"], 0)

    def test_road_access_requests_share_one_bounded_budget(self):
        prov = StubProvider(facilities=[
            _facility(lat=12.9717, lon=77.5947, facility_id="a-1"),
            _facility(category="fuel", subtype="fuel", lat=12.9720, lon=77.5975,
                      facility_id="b-1"),
        ])
        routing = StubRoutingProvider()
        svc = FacilitiesService(provider=prov)
        body = svc.get_facilities_for_routes(
            [
                {"route_id": "route-a", "polylines": [self.ROUTE_A]},
                {"route_id": "route-b", "polylines": [self.ROUTE_B]},
            ],
            radius_m=100,
            include_road_access=True,
            routing_provider=routing,
        )
        self.assertLessEqual(len(routing.requests), 6)
        self.assertTrue(any(
            f["road_travel_time_s"] is not None
            for route in body["routes"].values()
            for f in route["facilities"]
        ))

    def test_per_route_payload_contains_no_score_fields(self):
        prov = StubProvider(facilities=[_facility()])
        svc = FacilitiesService(provider=prov)
        body = svc.get_facilities_for_routes(
            [{"route_id": "route-a", "polylines": [self.ROUTE_A]}],
            radius_m=1000,
            include_road_access=False,
        )
        blob = str(body).lower()
        for banned in ("route_score", "segment_score", "safety_score", "hazard_density",
                       "severity"):
            self.assertNotIn(banned, blob)


if __name__ == "__main__":
    unittest.main()
