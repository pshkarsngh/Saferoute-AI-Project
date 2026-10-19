"""Regression: stale imagery must not justify a route recommendation (Rule 9).

Fix implemented: pipeline labels a route's evidence_class as "stale" when any
image used is stale (ImageryStatus.STALE or is_stale=True), and the
RouteComparer._is_sufficiently_assessed() returns False for stale evidence,
mirroring demo-evidence exclusion. Routes remain scored (is_available True for
STALE) but stale-evidence routes are ineligible for recommendation. A route
with only stale evidence cannot be recommended; mixed fresh/stale prefers the
fresh-assessed route. Missing imagery is never safe (all_routes_unassessed).
"""

import unittest

from src.imagery.interfaces import ImageryProvider
from src.imagery.schemas import ImageRef, ImageryResult, ImageryStatus
from datetime import datetime, timezone

SYN = "SYNTHETIC-"


class FreshImageryProvider(ImageryProvider):
    @property
    def provider_name(self):
        return "synthetic_fresh"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        ref = ImageRef(
            image_id=f"{SYN}FRESH-{segment.segment_id}",
            file_path=f"{SYN}frames/fresh.jpg",
            source="workspace_dashcam_v1", licence="CC-BY 4.0 (synthetic probe)",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            captured_at=datetime.now(timezone.utc).isoformat(),
            coordinates=None, distance_to_segment_m=None,
            is_stale=False, status="available")
        return ImageryResult(segment_id=segment.segment_id,
                             status=ImageryStatus.AVAILABLE, images=[ref])


class AllStaleImageryProvider(ImageryProvider):
    @property
    def provider_name(self):
        return "synthetic_all_stale"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        ref = ImageRef(
            image_id=f"{SYN}ALLSTALE-{segment.segment_id}",
            file_path=f"{SYN}frames/stale.jpg",
            source="workspace_dashcam_v1", licence="CC-BY 4.0 (synthetic probe)",
            retrieved_at="2026-10-18T00:00:00Z",
            captured_at="2020-01-01T00:00:00Z",
            coordinates=None, distance_to_segment_m=None,
            is_stale=True, status="stale")
        return ImageryResult(segment_id=segment.segment_id,
                             status=ImageryStatus.STALE, images=[ref])


class MissingImageryProvider(ImageryProvider):
    @property
    def provider_name(self):
        return "synthetic_missing"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        return ImageryResult(segment_id=segment.segment_id,
                             status=ImageryStatus.MISSING, images=[])


class PerRouteStaleProvider(ImageryProvider):
    """Returns stale imagery for one route and fresh imagery for another."""

    @property
    def provider_name(self):
        return "synthetic_per_route_stale"

    def __init__(self, stale_route_id):
        self.stale_route_id = stale_route_id

    def get_imagery_for_segment(self, segment, permitted_source=None):
        stale = segment.route_id == self.stale_route_id
        ref = ImageRef(
            image_id=f"{SYN}PR-{segment.segment_id}",
            file_path=f"{SYN}frames/pr.jpg",
            source="workspace_dashcam_v1", licence="CC-BY 4.0 (synthetic probe)",
            retrieved_at="2026-10-18T00:00:00Z",
            captured_at=("2020-01-01T00:00:00Z" if stale
                         else datetime.now(timezone.utc).isoformat()),
            coordinates=None, distance_to_segment_m=None,
            is_stale=stale, status=("stale" if stale else "available"))
        return ImageryResult(segment_id=segment.segment_id,
                             status=(ImageryStatus.STALE if stale else ImageryStatus.AVAILABLE),
                             images=[ref])


class CleanDetector:
    model_version = "saferoute-yolo11-v2"
    pipeline_version = "preprocess-v1"

    def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
        from src.detection.schemas import DetectionStatus, ImageDetectionResult
        return ImageDetectionResult(
            model_version=self.model_version, pipeline_version=self.pipeline_version,
            status=DetectionStatus.NO_DETECTIONS, image_id=image_id,
            route_id=route_id, segment_id=segment_id, detections=[],
            image_width=640, image_height=640, error=None, timing_ms={})


class HazardDetector:
    model_version = "saferoute-yolo11-v2"
    pipeline_version = "preprocess-v1"
    target_route_id = None

    def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
        from src.detection.schemas import DetectionRecord, DetectionStatus, ImageDetectionResult
        dets = []
        if route_id is not None and route_id == self.target_route_id:
            dets = [DetectionRecord(
                model_version=self.model_version, image_id=image_id,
                hazard_class="pothole", confidence=0.25,
                bbox_xyxy=[0.0, 0.0, 640.0, 192.0], bbox_norm=[0.0, 0.0, 1.0, 0.3],
                status="detected")]
        status = DetectionStatus.SUCCESS if dets else DetectionStatus.NO_DETECTIONS
        return ImageDetectionResult(
            model_version=self.model_version, pipeline_version=self.pipeline_version,
            status=status, image_id=image_id, route_id=route_id,
            segment_id=segment_id, detections=dets,
            image_width=640, image_height=640, error=None, timing_ms={})


class TestStaleImageryRegression(unittest.TestCase):
    def _api(self, imagery_provider, detector=None):
        from src.api.app import SafeRouteAPI
        from src.api.pipeline import SafetyAnalysisPipeline
        det = detector if detector else CleanDetector()
        pipeline = SafetyAnalysisPipeline(imagery_adapter=imagery_provider, detector=det)
        return SafeRouteAPI(pipeline=pipeline)

    def test_fresh_imagery_all_clean_tie_no_recommendation(self):
        api = self._api(FreshImageryProvider())
        code, rec = api.analyze({"destination": {"latitude": 12.9352, "longitude": 77.6245}})
        self.assertEqual(code, 200)
        comp = rec["comparison"]
        self.assertIsNone(comp["recommended_route_id"])
        self.assertEqual(comp["comparability"], "tied_scores")
        for r in rec["routes"]:
            self.assertEqual(r["evidence_class"], "real")

    def test_all_stale_evidence_no_recommendation(self):
        """All routes stale -> stale evidence_class -> ineligible -> no recommendation."""
        api = self._api(AllStaleImageryProvider())
        code, rec = api.analyze({"destination": {"latitude": 12.9352, "longitude": 77.6245}})
        self.assertEqual(code, 200)
        comp = rec["comparison"]
        self.assertIsNone(comp["recommended_route_id"])
        # stale routes are ineligible, so no candidate is sufficiently assessed
        self.assertEqual(comp["comparability"], "no_sufficiently_assessed_route")
        self.assertIn("stale", (comp.get("cannot_determine_reason") or "").lower())
        for e in comp["ranking"]:
            self.assertFalse(e["eligible_for_recommendation"])
            self.assertFalse(e["sufficiently_assessed"])
            self.assertEqual(e["evidence_class"], "stale")
        for r in rec["routes"]:
            self.assertEqual(r["evidence_class"], "stale")
            self.assertIn("stale", " ".join(r.get("limitations", [])).lower())

    def test_missing_imagery_all_unassessed(self):
        api = self._api(MissingImageryProvider())
        code, rec = api.analyze({"destination": {"latitude": 12.9352, "longitude": 77.6245}})
        self.assertEqual(code, 200)
        comp = rec["comparison"]
        self.assertIsNone(comp["recommended_route_id"])
        self.assertEqual(comp["comparability"], "all_routes_unassessed")

    def test_mixed_fresh_vs_stale_prefers_fresh(self):
        """Fresh route (with hazard) beats stale clean route (ineligible)."""
        det = HazardDetector()
        det.target_route_id = None  # will set after routes call
        code_routes, routes_obj = self._api(FreshImageryProvider(), det).routes(
            {"destination": {"latitude": 12.9352, "longitude": 77.6245}})
        self.assertEqual(code_routes, 200)
        route_ids = [r["route_id"] for r in routes_obj["routes"]]
        self.assertGreaterEqual(len(route_ids), 2)
        # route_ids[0] stale-only, route_ids[1] fresh; hazard on the fresh one so a naive
        # score comparison would prefer the stale-clean route.
        det.target_route_id = route_ids[1]
        api = self._api(PerRouteStaleProvider(stale_route_id=route_ids[0]), det)
        code, rec = api.analyze({"destination": {"latitude": 12.9352, "longitude": 77.6245}})
        self.assertEqual(code, 200)
        comp = rec["comparison"]
        # stale route ineligible -> fresh hazarded route is the only eligible candidate
        self.assertEqual(comp["recommended_route_id"], route_ids[1])
        rec_entry = next(e for e in comp["ranking"] if e["route_id"] == route_ids[1])
        stale_entry = next(e for e in comp["ranking"] if e["route_id"] == route_ids[0])
        self.assertTrue(rec_entry["eligible_for_recommendation"])
        self.assertFalse(stale_entry["eligible_for_recommendation"])
        self.assertEqual(stale_entry["evidence_class"], "stale")
        stale_route = next(r for r in rec["routes"] if r["route_id"] == route_ids[0])
        self.assertTrue(any("stale" in lim.lower()
                            for lim in stale_route.get("limitations", [])),
                        "stale limitation must be disclosed")


if __name__ == "__main__":
    unittest.main()
