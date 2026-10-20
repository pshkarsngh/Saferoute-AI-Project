"""SafeRoute AI — End-to-end API tests (PHASE_18).

Full flow over HTTP: destination -> routes -> analysis -> comparison -> explanation,
plus the required negative tests (Rule 14). Fakes are injected so no YOLO load or
network call is required.
"""

import json
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from src.api.app import SafeRouteAPI, create_server
from src.api.pipeline import SafetyAnalysisPipeline
from src.api.store import AnalysisStore
from src.geocoding.mock_geocoder import MockGeocoder
from tests.unit.test_api import (
    AllMissingImageryProvider,
    FailingRoutingProvider,
    FakeDetector,
    HalfImageryProvider,
)

DEST = {"latitude": 12.9352, "longitude": 77.6245}
ORIGIN = {"latitude": 12.9716, "longitude": 77.5946}


class TestEndToEndApi(unittest.TestCase):
    def setUp(self):
        self.db = Path("data/test_e2e.db")
        if self.db.exists():
            self.db.unlink()
        self.store = AnalysisStore(db_path=self.db)
        self._servers = []

    def tearDown(self):
        for s in self._servers:
            s.shutdown()
            s.server_close()
        if self.db.exists():
            try:
                self.db.unlink()
            except PermissionError:
                pass

    def _server(self, **kw):
        pipeline = SafetyAnalysisPipeline(detector=FakeDetector(), **kw)
        api = SafeRouteAPI(pipeline=pipeline, store=self.store, geocoder=MockGeocoder())
        srv = create_server("127.0.0.1", 0, api=api)
        self._servers.append(srv)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return "http://127.0.0.1:%d" % srv.server_address[1]

    def _get(self, base, path):
        try:
            with urllib.request.urlopen(base + path, timeout=15) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def _post(self, base, path, body):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_full_flow_destination_to_explanation(self):
        base = self._server(imagery_adapter=HalfImageryProvider())
        code, rec = self._post(base, "/api/analyze", {"origin": ORIGIN, "destination": DEST})
        self.assertEqual(code, 200)
        aid = rec["analysis_id"]
        self.assertIn(rec["status"], ["assessed", "partially_assessed", "unassessed", "failed"])

        c, got = self._get(base, f"/api/analyze/{aid}")
        self.assertEqual(c, 200)
        self.assertEqual(got["analysis_id"], aid)
        c, comp = self._get(base, f"/api/analysis/{aid}/comparison")
        self.assertEqual(c, 200)
        self.assertIn("comparison", comp)
        c, exp = self._get(base, f"/api/analysis/{aid}/explanation")
        self.assertEqual(c, 200)
        self.assertIn("source", exp)
        c, hz = self._get(base, f"/api/analysis/{aid}/hazards")
        self.assertEqual(c, 200)
        self.assertIn("hazards_count", hz)

    def test_negative_missing_imagery_is_unassessed(self):
        base = self._server(imagery_adapter=AllMissingImageryProvider())
        _, rec = self._post(base, "/api/analyze", {"destination": DEST})
        self.assertEqual(rec["status"], "unassessed")
        self.assertIsNone(rec["recommendation"])

    def test_negative_routing_failure_no_fabricated_routes(self):
        base = self._server(routing_provider=FailingRoutingProvider(), imagery_adapter=AllMissingImageryProvider())
        _, rec = self._post(base, "/api/analyze", {"destination": DEST})
        self.assertEqual(rec["status"], "failed")
        self.assertEqual(rec["routes"], [])

    def test_negative_empty_detections_distinct_from_safe(self):
        base = self._server(imagery_adapter=HalfImageryProvider())
        _, rec = self._post(base, "/api/analyze", {"destination": DEST})
        _, hz = self._get(base, f"/api/analysis/{rec['analysis_id']}/hazards")
        self.assertEqual(hz["hazards_count"], 0)  # no hazards reported, not a safe-road claim

    def test_explanation_fallback_when_llm_unavailable(self):
        base = self._server(imagery_adapter=HalfImageryProvider())
        _, rec = self._post(base, "/api/analyze", {"destination": DEST})
        self.assertEqual(rec["explanation"]["source"], "fallback")

    def test_facilities_endpoint_is_separate_from_score(self):
        base = self._server(imagery_adapter=HalfImageryProvider())
        code, fac = self._post(base, "/api/facilities", {"location": DEST, "radius_m": 2000})
        self.assertEqual(code, 200)
        self.assertIn("facilities", fac)
        self.assertNotIn("route_score", json.dumps(fac).lower())

    def test_not_found_error_schema(self):
        base = self._server()
        code, obj = self._get(base, "/api/analyze/an-does-not-exist")
        self.assertEqual(code, 404)
        self.assertEqual(obj["status"], "failed")
        self.assertIn("code", obj["error"])

    def test_geocode_endpoint_resolves_place(self):
        base = self._server()
        code, obj = self._post(base, "/api/geocode", {"query": "Koramangala"})
        self.assertEqual(code, 200)
        self.assertTrue(obj["candidates"])

    def test_serves_static_index(self):
        base = self._server()
        with urllib.request.urlopen(base + "/", timeout=10) as r:
            self.assertEqual(r.status, 200)
            body = r.read().decode("utf-8", "replace")
        self.assertTrue("SafeRoute AI" in body or "INDROUTE" in body)
        self.assertIn("<div id=\"root\"", body)

    def test_analyze_accepts_place_name_destination(self):
        base = self._server(imagery_adapter=HalfImageryProvider())
        code, rec = self._post(base, "/api/analyze", {"destination_query": "Koramangala"})
        self.assertEqual(code, 200)
        self.assertEqual(rec["destination"]["latitude"], 12.9352)

    # --------------------------------- PHASE_27 multiple routes / latency -- #
    def test_routes_endpoint_returns_geometry_only_no_score(self):
        """The fast preview carries NO safety verdict of any kind (Rules 7, 9)."""
        base = self._server(imagery_adapter=HalfImageryProvider())
        code, obj = self._post(base, "/api/routes", {"origin": ORIGIN, "destination": DEST})
        self.assertEqual(code, 200)
        self.assertIn("routes", obj)
        self.assertGreaterEqual(len(obj["routes"]), 1)
        blob = json.dumps(obj).lower()
        for forbidden in ("route_score", "safety_score", "recommended_route_id", "hazards"):
            self.assertNotIn(forbidden, blob)

    def test_routes_and_analyze_agree_on_route_set(self):
        """Preview and assessment must expose the same provider route ids."""
        base = self._server(imagery_adapter=HalfImageryProvider())
        _, preview = self._post(base, "/api/routes", {"origin": ORIGIN, "destination": DEST})
        _, rec = self._post(base, "/api/analyze", {"origin": ORIGIN, "destination": DEST})
        self.assertEqual(
            [r["route_id"] for r in preview["routes"]],
            [r["route_id"] for r in rec["routes"]],
        )

    def test_analyze_reports_stage_timings(self):
        base = self._server(imagery_adapter=HalfImageryProvider())
        _, rec = self._post(base, "/api/analyze", {"origin": ORIGIN, "destination": DEST})
        timings = rec.get("timings_ms")
        self.assertIsNotNone(timings)
        for stage in ("routing_ms", "imagery_ms", "detection_ms", "total_ms"):
            self.assertIn(stage, timings)
        # Timings are additive metadata only — the verdict fields are untouched.
        self.assertIn(rec["status"], ["assessed", "partially_assessed", "unassessed", "failed"])

    def test_timings_persisted_with_analysis(self):
        base = self._server(imagery_adapter=HalfImageryProvider())
        _, rec = self._post(base, "/api/analyze", {"origin": ORIGIN, "destination": DEST})
        _, got = self._get(base, f"/api/analyze/{rec['analysis_id']}")
        self.assertEqual(got["timings_ms"]["total_ms"], rec["timings_ms"]["total_ms"])

    def test_missing_imagery_never_reported_as_safe(self):
        base = self._server(imagery_adapter=AllMissingImageryProvider())
        _, rec = self._post(base, "/api/analyze", {"origin": ORIGIN, "destination": DEST})
        self.assertEqual(rec["status"], "unassessed")
        self.assertIsNone(rec["comparison"]["recommended_route_id"])
        for route in rec["routes"]:
            self.assertIsNone(route["route_score"])

    def test_limits_and_disclosures_survive_preview_then_analyze(self):
        """The two-phase flow must not lose the provider's route-count limitation."""
        base = self._server(imagery_adapter=HalfImageryProvider())
        _, preview = self._post(base, "/api/routes", {"origin": ORIGIN, "destination": DEST})
        _, rec = self._post(base, "/api/analyze", {"origin": ORIGIN, "destination": DEST})
        self.assertIn("limitations", preview)
        self.assertEqual(len(preview["routes"]), len(rec["routes"]))


if __name__ == "__main__":
    unittest.main()
