"""SafeRoute AI — Unit tests for the Backend API pipeline (PHASE_16).

Uses injected fakes (no YOLO load, no network) for deterministic, fast tests,
including the required negative tests (Rule 9, 10, 12, 14).
"""

import json
import http.client
import sqlite3
import threading
import unittest
import urllib.request
from datetime import datetime, timezone

from src.api.app import MAX_REQUEST_BYTES, SafeRouteAPI, create_server
from src.api.pipeline import SafetyAnalysisPipeline
from src.api.store import AnalysisStore
from src.geocoding.mock_geocoder import MockGeocoder
from src.detection.schemas import DetectionRecord, DetectionStatus, ImageDetectionResult
from src.imagery.interfaces import ImageryProvider
from src.imagery.schemas import ImageRef, ImageryResult, ImageryStatus
from src.routing.schemas import Coordinate, RouteResponse, RoutingStatus

ORIGIN = Coordinate(12.9716, 77.5946)
DEST = Coordinate(12.9352, 77.6245)
# PHASE_44: the API no longer substitutes a default origin. Tests that need a
# full route analysis must supply valid coordinates explicitly.
ORIGIN_PAYLOAD = {"latitude": ORIGIN.latitude, "longitude": ORIGIN.longitude}
DEST_PAYLOAD = {"latitude": DEST.latitude, "longitude": DEST.longitude}


class FakeDetector:
    """Returns NO_DETECTIONS for every image (distinct from 'safe road')."""
    model_version = "saferoute-yolo11-v1"
    pipeline_version = "preprocess-v1"

    def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
        return ImageDetectionResult(
            model_version=self.model_version, pipeline_version=self.pipeline_version,
            status=DetectionStatus.NO_DETECTIONS, image_id=image_id,
            route_id=route_id, segment_id=segment_id, detections=[],
            image_width=640, image_height=640, error=None, timing_ms={},
        )


class SinglePotholeDetector:
    """Returns exactly one supported 'pothole' detection per image (deterministic)."""
    model_version = "saferoute-yolo11-v1"
    pipeline_version = "preprocess-v1"

    def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
        return ImageDetectionResult(
            model_version=self.model_version, pipeline_version=self.pipeline_version,
            status=DetectionStatus.SUCCESS, image_id=image_id,
            route_id=route_id, segment_id=segment_id,
            detections=[DetectionRecord(
                model_version=self.model_version, image_id=image_id,
                route_id=route_id, segment_id=segment_id,
                hazard_class="pothole", confidence=0.9,
                bbox_xyxy=[10.0, 10.0, 50.0, 50.0],
                bbox_norm=[0.01, 0.01, 0.08, 0.08], status="detected")],
            image_width=640, image_height=640, error=None, timing_ms={},
        )


class HalfImageryProvider(ImageryProvider):
    """Deterministic imagery: even segments have imagery, odd segments are MISSING."""
    @property
    def provider_name(self):
        return "half_imagery"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        seq = int(segment.segment_id.rsplit("-", 1)[-1])
        if seq % 2 == 0:
            now = datetime.now(timezone.utc).isoformat()
            return ImageryResult(
                segment_id=segment.segment_id, status=ImageryStatus.AVAILABLE,
                images=[ImageRef(image_id=f"img-{segment.segment_id}", file_path="x.jpg",
                                 source="workspace_dashcamp_v1", licence="CC-BY 4.0", retrieved_at=now)],
                source="workspace_dashcamp_v1", licence="CC-BY 4.0", limitations=[])
        return ImageryResult(
            segment_id=segment.segment_id, status=ImageryStatus.MISSING,
            images=[], source="workspace_dashcamp_v1", licence="CC-BY 4.0",
            limitations=["missing_imagery_not_safe"])


class AllMissingImageryProvider(ImageryProvider):
    @property
    def provider_name(self):
        return "all_missing"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        return ImageryResult(segment_id=segment.segment_id, status=ImageryStatus.MISSING,
                             images=[], limitations=["missing_imagery_not_safe"])


class TestApiPipeline(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        self.db = Path("data/test_api.db")
        if self.db.exists():
            self.db.unlink()
        store = AnalysisStore(db_path=self.db)
        self.pipeline = SafetyAnalysisPipeline(
            imagery_adapter=HalfImageryProvider(), detector=FakeDetector())
        self.api = SafeRouteAPI(pipeline=self.pipeline, store=store, geocoder=MockGeocoder())

    def tearDown(self):
        if self.db.exists():
            self.db.unlink()

    def test_health_ok(self):
        code, obj = self.api.health()
        self.assertEqual(code, 200)
        self.assertEqual(obj["status"], "ok")

    def test_model_identity_is_registered(self):
        """The resolved checkpoint identity is persisted for provenance."""
        conn = sqlite3.connect(str(self.db))
        try:
            rows = conn.execute(
                "SELECT id, name, metrics_json FROM model_versions").fetchall()
        finally:
            conn.close()
        self.assertTrue(rows, "startup must register the model identity")
        version = self.pipeline.model_version
        match = [row for row in rows if row[0] == version]
        self.assertTrue(match, f"no model_versions row for {version!r}")
        identity = json.loads(match[0][2])["identity"]
        self.assertEqual(identity["model_version"], version)
        self.assertIn("validated", identity)

    def test_routes_returns_routes(self):
        code, obj = self.api.routes({"origin": ORIGIN_PAYLOAD, "destination": DEST_PAYLOAD})
        self.assertEqual(code, 200)
        self.assertGreaterEqual(len(obj["routes"]), 1)

    def test_partial_imagery_yields_partially_assessed(self):
        code, rec = self.api.analyze({"origin": ORIGIN_PAYLOAD, "destination": DEST_PAYLOAD})
        self.assertEqual(code, 200)
        self.assertEqual(rec["status"], "partially_assessed")
        # Some segments lack imagery -> their score is None (never a safe verdict).
        any_none = any(
            s.get("segment_score") is None
            for r in rec["routes"] for s in r.get("segment_scores", [])
        )
        self.assertTrue(any_none)

    def test_all_missing_imagery_is_unassessed_not_safe(self):
        pipeline = SafetyAnalysisPipeline(imagery_adapter=AllMissingImageryProvider(), detector=FakeDetector())
        api = SafeRouteAPI(pipeline=pipeline, store=self.api.store)
        code, rec = api.analyze({"origin": ORIGIN_PAYLOAD, "destination": DEST_PAYLOAD})
        self.assertEqual(code, 200)
        self.assertEqual(rec["status"], "unassessed")
        self.assertIsNone(rec["recommendation"])
        self.assertEqual(rec["comparison"]["ranking"], [])
        for r in rec["routes"]:
            self.assertIsNone(r["route_score"])

    def test_invalid_coordinates_rejected(self):
        code, obj = self.api.analyze({"origin": ORIGIN_PAYLOAD, "destination": "zzzz nowhere place xyz"})
        self.assertEqual(code, 400)
        self.assertEqual(obj["status"], "failed")
        self.assertIn("code", obj["error"])

    def test_place_name_destination_geocoded(self):
        code, rec = self.api.analyze({"origin": ORIGIN_PAYLOAD, "destination_query": "Koramangala"})
        self.assertEqual(code, 200)
        self.assertEqual(rec["destination"]["latitude"], 12.9352)

    # ----------------------------- PHASE_44 coordinate validation ------ #
    def test_missing_origin_rejected(self):
        """No default origin is substituted; omitting it is a 400."""
        code, obj = self.api.analyze({"destination": DEST_PAYLOAD})
        self.assertEqual(code, 400)
        self.assertEqual(obj["error"]["code"], "missing_location")
        self.assertIn("origin", obj["error"]["message"])

    def test_missing_destination_rejected(self):
        code, obj = self.api.analyze({"origin": ORIGIN_PAYLOAD})
        self.assertEqual(code, 400)
        self.assertEqual(obj["error"]["code"], "missing_location")
        self.assertIn("destination", obj["error"]["message"])

    def test_malformed_coordinates_rejected(self):
        cases = [
            {"latitude": "not-a-number", "longitude": 77.5946},
            {"latitude": 12.9716},
            [12.9716],
            [],
        ]
        for origin in cases:
            with self.subTest(origin=origin):
                code, obj = self.api.analyze({"origin": origin, "destination": DEST_PAYLOAD})
                self.assertEqual(code, 400)
                self.assertEqual(obj["error"]["code"], "invalid_coordinates")

    def test_out_of_range_coordinates_rejected(self):
        cases = [
            {"latitude": 91.0, "longitude": 77.5946},
            {"latitude": -91.0, "longitude": 77.5946},
            {"latitude": 12.9716, "longitude": 181.0},
            {"latitude": 12.9716, "longitude": -181.0},
            {"latitude": float("nan"), "longitude": 77.5946},
            {"latitude": float("inf"), "longitude": 77.5946},
        ]
        for origin in cases:
            with self.subTest(origin=origin):
                code, obj = self.api.analyze({"origin": origin, "destination": DEST_PAYLOAD})
                self.assertEqual(code, 400)
                self.assertEqual(obj["error"]["code"], "invalid_coordinates")


class FailingRoutingProvider:
    provider_name = "failing"

    def get_routes(self, request):
        return RouteResponse(
            status=RoutingStatus.PROVIDER_TIMEOUT, provider="failing", routes=[],
            limitations=["routing_request_timed_out_after_max_retries"],
            error_message="Timed out.")


class TestApiNegativeAndHttp(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        self.db = Path("data/test_api2.db")
        if self.db.exists():
            self.db.unlink()
        self.store = AnalysisStore(db_path=self.db)

    def tearDown(self):
        if self.db.exists():
            self.db.unlink()

    def _api(self, **kw):
        pipeline = SafetyAnalysisPipeline(detector=FakeDetector(), **kw)
        return SafeRouteAPI(pipeline=pipeline, store=self.store, geocoder=MockGeocoder())

    def test_routing_failure_surfaces_error_no_fabricated_routes(self):
        api = self._api(routing_provider=FailingRoutingProvider(), imagery_adapter=AllMissingImageryProvider())
        code, rec = api.analyze({"origin": ORIGIN_PAYLOAD, "destination": DEST_PAYLOAD})
        self.assertEqual(code, 200)
        self.assertEqual(rec["status"], "failed")
        self.assertEqual(rec["routes"], [])

    def test_explanation_fallback_when_llm_disabled(self):
        api = self._api(imagery_adapter=AllMissingImageryProvider())
        _, rec = api.analyze({"origin": ORIGIN_PAYLOAD, "destination": DEST_PAYLOAD})
        exp = rec["explanation"]
        self.assertEqual(exp["source"], "fallback")
        self.assertTrue(exp["explanation"])

    def test_store_roundtrip(self):
        api = self._api(imagery_adapter=AllMissingImageryProvider())
        _, rec = api.analyze({"origin": ORIGIN_PAYLOAD, "destination": DEST_PAYLOAD})
        code, got = api.get_analysis(rec["analysis_id"])
        self.assertEqual(code, 200)
        self.assertIsNotNone(got)
        self.assertEqual(got["analysis_id"], rec["analysis_id"])

    # --------------------------------- hazard_detections (PHASE_25) ------ #
    def _detecting_api(self, detector):
        pipeline = SafetyAnalysisPipeline(imagery_adapter=HalfImageryProvider(),
                                          detector=detector)
        return SafeRouteAPI(pipeline=pipeline, store=self.store, geocoder=MockGeocoder())

    def _hazard_rows(self, analysis_id):
        import sqlite3
        conn = sqlite3.connect(str(self.db))
        try:
            rows = conn.execute(
                "SELECT analysis_id, route_id, segment_id, image_id, hazard_class, "
                "confidence, severity, bbox_json, status FROM hazard_detections "
                "WHERE analysis_id=?", (analysis_id,)).fetchall()
        finally:
            conn.close()
        return rows

    def test_hazard_detections_persisted_for_audit(self):
        """Recorded detections are queryable, with the model/config audit fields."""
        api = self._detecting_api(SinglePotholeDetector())
        _, rec = api.analyze({"origin": ORIGIN_PAYLOAD, "destination": DEST_PAYLOAD})
        rows = self._hazard_rows(rec["analysis_id"])
        self.assertTrue(rows, "supported detections must be persisted for audit (Rule 17)")
        row = rows[0]
        self.assertEqual(row[0], rec["analysis_id"])
        self.assertTrue(row[1])            # route_id
        self.assertTrue(row[3])            # image_id
        self.assertEqual(row[4], "pothole")
        self.assertAlmostEqual(row[5], 0.9, places=4)   # confidence
        self.assertIn("bbox_xyxy", json.loads(row[7]))
        self.assertEqual(row[8], "assessed")   # HazardRecord assessment status
        # Must match the hazards already exposed by the read API.
        code, haz = api.hazards(rec["analysis_id"])
        self.assertEqual(code, 200)
        self.assertEqual(len(haz["hazards"]), len(rows))

    def test_hazard_detections_idempotent_on_resave(self):
        """Re-saving the same analysis must not duplicate detection rows."""
        api = self._detecting_api(SinglePotholeDetector())
        _, rec = api.analyze({"origin": ORIGIN_PAYLOAD, "destination": DEST_PAYLOAD})
        first = len(self._hazard_rows(rec["analysis_id"]))
        self.assertGreater(first, 0)
        self.store.save_analysis(rec)
        self.store.save_analysis(rec)
        self.assertEqual(len(self._hazard_rows(rec["analysis_id"])), first)

    def test_hazard_detections_empty_when_none_detected(self):
        """No detections -> no rows (an absence is never recorded as a hazard)."""
        api = self._detecting_api(FakeDetector())
        _, rec = api.analyze({"origin": ORIGIN_PAYLOAD, "destination": DEST_PAYLOAD})
        self.assertEqual(self._hazard_rows(rec["analysis_id"]), [])

    def test_http_health_endpoint(self):
        api = self._api()
        server = create_server("127.0.0.1", 0, api=api)
        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=10) as r:
                self.assertEqual(r.status, 200)
                body = json.loads(r.read().decode())
                self.assertEqual(body["status"], "ok")
                # Deployment hardening: standard response headers are present.
                self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
                self.assertEqual(r.headers.get("Referrer-Policy"), "no-referrer")
                # The reported bind address must be the live one, not the
                # configured default (the process may run on --port 8765).
                self.assertEqual(body["effective_bind"]["port"], port)
                self.assertEqual(api.effective_port, port)
        finally:
            server.shutdown()
            server.server_close()

    def test_oversized_request_body_is_rejected(self):
        api = self._api()
        server = create_server("127.0.0.1", 0, api=api)
        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.putrequest("POST", "/api/analyze")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", str(MAX_REQUEST_BYTES + 1))
            conn.endheaders()
            resp = conn.getresponse()
            body = json.loads(resp.read().decode())
            self.assertEqual(resp.status, 413)
            self.assertEqual(body["error"]["code"], "payload_too_large")
            conn.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
