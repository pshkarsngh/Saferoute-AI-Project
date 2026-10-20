"""SafeRoute AI — multiple-route delivery, latency instrumentation and
duplicate-work elimination (PHASE_27).

These tests lock in the four properties the PHASE_27 work depends on:

1. Every distinct route the provider returns is analysed and returned — never
   padded, never dropped (Rule 10).
2. Each response carries an additive `timings_ms` breakdown so the dominant
   cost is measurable from a real response.
3. A downloaded frame that several segments share is inferred ONCE per analysis
   request, with results re-stamped per segment so the evidence is identical to
   the un-memoised path.
4. Missing / stale imagery is never promoted to a "safe" verdict.

All fakes are injected: no YOLO load, no network, no .env access.
"""

import threading
import time
import unittest
from datetime import datetime, timezone

from src.api.pipeline import SafetyAnalysisPipeline
from src.detection.schemas import DetectionStatus, ImageDetectionResult
from src.imagery.interfaces import ImageryProvider
from src.imagery.schemas import ImageRef, ImageryResult, ImageryStatus
from src.routing.schemas import (
    Coordinate,
    Route,
    RouteGeometry,
    RouteResponse,
    RouteSegment,
    RoutingStatus,
)

ORIGIN = Coordinate(12.9716, 77.5946)
DEST = Coordinate(12.9352, 77.6245)


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
def _segment(seq: int, route_id: str = "rt-a") -> RouteSegment:
    return RouteSegment(
        segment_id=f"seg-{route_id}-{seq:04d}",
        route_id=route_id,
        sequence=seq,
        length_m=100.0,
        duration_s=10.0,
        start_coord=Coordinate(12.97, 77.60 + seq * 0.001),
        end_coord=Coordinate(12.98, 77.61 + seq * 0.001),
        geometry=RouteGeometry(
            coordinates=[(77.60 + seq * 0.001, 12.97), (77.61 + seq * 0.001, 12.98)]
        ),
    )


def _route(segments, route_id: str = "rt-a", summary: str = "Route 1 via Test Road") -> Route:
    return Route(
        route_id=route_id,
        provider="test",
        summary=summary,
        distance_m=1000.0,
        duration_s=100.0,
        geometry=RouteGeometry(coordinates=[(77.60, 12.97), (77.61, 12.98)]),
        segments=list(segments),
        limitations=[],
    )


class MultiRouteProvider:
    """Routing provider returning exactly the caller-supplied routes."""

    def __init__(self, routes):
        self._routes = list(routes)

    @property
    def provider_name(self):
        return "multi_route_test"

    def get_routes(self, request):
        return RouteResponse(
            status=RoutingStatus.OK,
            provider=self.provider_name,
            routes=list(self._routes),
            request_id="req-test",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            limitations=(
                ["fewer_than_four_routes_returned"] if len(self._routes) < 4 else []
            ),
        )


class SharedImageProvider(ImageryProvider):
    """Every segment returns the SAME single image (same path + image id).

    Mirrors the live Mapillary case where several adjacent segments snap to one
    captured frame. This is what makes duplicate YOLO inference observable.
    """

    def __init__(self):
        self.calls = 0

    @property
    def provider_name(self):
        return "shared_image"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        self.calls += 1
        now = datetime.now(timezone.utc).isoformat()
        return ImageryResult(
            segment_id=segment.segment_id,
            status=ImageryStatus.AVAILABLE,
            images=[
                ImageRef(
                    image_id="img-shared",
                    file_path="shared.jpg",
                    source="workspace_dashcamp_v1",
                    licence="CC-BY 4.0",
                    retrieved_at=now,
                )
            ],
            source="workspace_dashcamp_v1",
            licence="CC-BY 4.0",
            limitations=[],
        )


class CountingDetector:
    """Deterministic detector that records how many inferences were requested."""

    model_version = "saferoute-yolo11-v1"
    pipeline_version = "preprocess-v1"

    def __init__(self):
        self.inferences = 0
        self.lock = threading.Lock()

    def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
        with self.lock:
            self.inferences += 1
        return ImageDetectionResult(
            model_version=self.model_version,
            pipeline_version=self.pipeline_version,
            status=DetectionStatus.NO_DETECTIONS,
            image_id=image_id,
            route_id=route_id,
            segment_id=segment_id,
            detections=[],
            image_width=640,
            image_height=640,
            error=None,
            timing_ms={},
        )


class MissingImageryProvider(ImageryProvider):

    @property
    def provider_name(self):
        return "all_missing"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        return ImageryResult(
            segment_id=segment.segment_id,
            status=ImageryStatus.MISSING,
            images=[],
            limitations=["missing_imagery_not_safe"],
        )


class PotholeDetector(CountingDetector):
    """One supported 'pothole' detection per inference, so routes actually score."""

    def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
        from src.detection.schemas import DetectionRecord

        result = super().detect(
            image_input, image_id=image_id, route_id=route_id,
            segment_id=segment_id, conf=conf,
        )
        result.status = DetectionStatus.SUCCESS
        result.detections = [
            DetectionRecord(
                model_version=self.model_version, image_id=image_id,
                route_id=route_id, segment_id=segment_id,
                hazard_class="pothole", confidence=0.9,
                bbox_xyxy=[10.0, 10.0, 50.0, 50.0],
                bbox_norm=[0.01, 0.01, 0.08, 0.08], status="detected",
            )
        ]
        return result


class StaleImageryProvider(ImageryProvider):
    """Imagery that is present but explicitly flagged stale."""

    @property
    def provider_name(self):
        return "stale"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        now = datetime.now(timezone.utc).isoformat()
        return ImageryResult(
            segment_id=segment.segment_id,
            status=ImageryStatus.AVAILABLE,
            images=[
                ImageRef(
                    image_id=f"stale-{segment.segment_id}",
                    file_path="stale.jpg",
                    source="workspace_dashcamp_v1",
                    licence="CC-BY 4.0",
                    retrieved_at=now,
                    is_stale=True,
                )
            ],
            source="workspace_dashcamp_v1",
            licence="CC-BY 4.0",
            limitations=["stale_imagery"],
        )


def _two_routes():
    return [
        _route([_segment(i, "rt-a") for i in range(4)], "rt-a", "Route 1 via A Road"),
        _route([_segment(i, "rt-b") for i in range(4, 8)], "rt-b", "Route 2 via B Road"),
    ]


# --------------------------------------------------------------------------- #
# 1. Multiple distinct routes
# --------------------------------------------------------------------------- #
class TestMultipleRoutesReturned(unittest.TestCase):
    def test_two_distinct_routes_are_both_returned_and_ordered(self):
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(_two_routes()),
            imagery_adapter=MissingImageryProvider(),
            detector=CountingDetector(),
            imagery_workers=4,
        )
        record = pipeline.analyze(ORIGIN, DEST)

        self.assertEqual(len(record["routes"]), 2, "pipeline must not drop routes")
        self.assertEqual([r["route_id"] for r in record["routes"]], ["rt-a", "rt-b"])
        # Every route is scored/assessed independently, not aliased to one row.
        self.assertEqual(len({r["route_id"] for r in record["routes"]}), 2)

    def test_each_route_keeps_its_own_geometry_and_summary(self):
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(_two_routes()),
            imagery_adapter=MissingImageryProvider(),
            detector=CountingDetector(),
        )
        record = pipeline.analyze(ORIGIN, DEST)
        summaries = [r["summary"] for r in record["routes"]]
        self.assertEqual(summaries, ["Route 1 via A Road", "Route 2 via B Road"])
        for route in record["routes"]:
            self.assertIn("geometry", route)
            self.assertGreaterEqual(len(route["geometry"]["coordinates"]), 2)

    def test_ranking_covers_exactly_the_returned_routes(self):
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(_two_routes()),
            imagery_adapter=SharedImageProvider(),
            detector=PotholeDetector(),
        )
        record = pipeline.analyze(ORIGIN, DEST)
        ranking_ids = sorted(e["route_id"] for e in record["comparison"]["ranking"])
        self.assertEqual(ranking_ids, ["rt-a", "rt-b"])

    def test_single_route_is_never_padded(self):
        one = [_route([_segment(i) for i in range(3)], "rt-solo", "Route 1 via Solo Road")]
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(one),
            imagery_adapter=MissingImageryProvider(),
            detector=CountingDetector(),
        )
        record = pipeline.analyze(ORIGIN, DEST)
        self.assertEqual(len(record["routes"]), 1)
        self.assertIn("fewer_than_four_routes_returned", record["limitations"])


# --------------------------------------------------------------------------- #
# 2. Latency instrumentation
# --------------------------------------------------------------------------- #
class TestLatencyInstrumentation(unittest.TestCase):
    def test_analysis_record_carries_stage_timings(self):
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(_two_routes()),
            imagery_adapter=MissingImageryProvider(),
            detector=CountingDetector(),
            imagery_workers=4,
        )
        record = pipeline.analyze(ORIGIN, DEST)

        timings = record["timings_ms"]
        for stage in (
            "routing_ms",
            "imagery_ms",
            "detection_ms",
            "risk_scoring_ms",
            "comparison_ms",
            "explanation_ms",
            "total_ms",
        ):
            self.assertIn(stage, timings)
            self.assertGreaterEqual(timings[stage], 0.0)

        self.assertGreaterEqual(timings["total_ms"], 0.0)
        # The instrumentation is observational only — it must not fabricate a
        # total smaller than the routing leg it wraps.
        self.assertGreaterEqual(timings["total_ms"] + 1e-6, timings["routing_ms"])

    def test_per_route_timings_are_present(self):
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(_two_routes()),
            imagery_adapter=MissingImageryProvider(),
            detector=CountingDetector(),
        )
        record = pipeline.analyze(ORIGIN, DEST)
        for route in record["routes"]:
            self.assertIn("timings_ms", route)
            self.assertIn("detection_ms", route["timings_ms"])
            self.assertIn("risk_scoring_ms", route["timings_ms"])

    def test_detection_timing_reflects_measured_inference(self):
        """A slow detector must show up in the reported detection stage."""

        class SlowDetector(CountingDetector):
            def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
                time.sleep(0.02)
                return super().detect(
                    image_input, image_id=image_id, route_id=route_id,
                    segment_id=segment_id, conf=conf,
                )

        routes = [_route([_segment(i) for i in range(4)], "rt-slow", "Route 1 via Slow Road")]
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(routes),
            imagery_adapter=SharedImageProvider(),
            detector=SlowDetector(),
        )
        record = pipeline.analyze(ORIGIN, DEST)
        # 4 segments share one image => exactly one inference of >= 20 ms.
        self.assertGreaterEqual(record["timings_ms"]["detection_ms"], 15.0)


# --------------------------------------------------------------------------- #
# 3. Duplicate-inference elimination (detection memo)
# --------------------------------------------------------------------------- #
class TestDetectionMemo(unittest.TestCase):
    def test_shared_frame_is_inferred_only_once(self):
        detector = CountingDetector()
        routes = [_route([_segment(i) for i in range(6)], "rt-a", "Route 1 via Shared Road")]
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(routes),
            imagery_adapter=SharedImageProvider(),
            detector=detector,
            imagery_workers=4,
        )
        pipeline.analyze(ORIGIN, DEST)
        self.assertEqual(
            detector.inferences, 1,
            "one shared frame across 6 segments must trigger exactly one YOLO inference",
        )

    def test_memo_spans_routes_in_one_request(self):
        detector = CountingDetector()
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(_two_routes()),
            imagery_adapter=SharedImageProvider(),
            detector=detector,
            imagery_workers=4,
        )
        pipeline.analyze(ORIGIN, DEST)
        self.assertEqual(detector.inferences, 1)

    def test_memo_does_not_change_evidence(self):
        """Memoised and un-memoised runs must produce identical assessments."""
        memo_pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(_two_routes()),
            imagery_adapter=SharedImageProvider(),
            detector=CountingDetector(),
            imagery_workers=4,
        )
        memo_record = memo_pipeline.analyze(ORIGIN, DEST)

        # Control: identical pipeline with the per-route memo forced empty, which
        # reproduces the pre-memo behaviour of one inference per segment.
        control_detector = CountingDetector()
        control_pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(_two_routes()),
            imagery_adapter=SharedImageProvider(),
            detector=control_detector,
            imagery_workers=4,
        )
        original = control_pipeline._analyze_route

        def per_route_cache(route, imagery_by_index=None, detection_cache=None):
            return original(route, imagery_by_index, detection_cache={})

        control_pipeline._analyze_route = per_route_cache  # type: ignore[assignment]
        control_record = control_pipeline.analyze(ORIGIN, DEST)

        self.assertGreater(control_detector.inferences, 1, "control run must not be memoised")
        self.assertEqual(
            [
                (r["route_id"], r["route_score"], r["status"], r["hazards_total"])
                for r in memo_record["routes"]
            ],
            [
                (r["route_id"], r["route_score"], r["status"], r["hazards_total"])
                for r in control_record["routes"]
            ],
        )
        self.assertEqual(memo_record["recommendation"], control_record["recommendation"])


# --------------------------------------------------------------------------- #
# 4. Missing / stale imagery is never "safe"
# --------------------------------------------------------------------------- #
class TestMissingAndStaleImagery(unittest.TestCase):
    def test_missing_imagery_is_unassessed_not_safe(self):
        routes = [_route([_segment(i) for i in range(4)], "rt-miss", "Route 1 via Missing Road")]
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(routes),
            imagery_adapter=MissingImageryProvider(),
            detector=CountingDetector(),
        )
        record = pipeline.analyze(ORIGIN, DEST)
        self.assertEqual(record["status"], "unassessed")
        self.assertIsNone(record["recommendation"])
        for route in record["routes"]:
            self.assertIsNone(route["route_score"])

    def test_stale_imagery_is_labelled_and_not_recommended(self):
        routes = [
            _route([_segment(i, "rt-a") for i in range(4)], "rt-a", "Route 1 via A Road"),
            _route([_segment(i, "rt-b") for i in range(4, 8)], "rt-b", "Route 2 via B Road"),
        ]
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(routes),
            imagery_adapter=StaleImageryProvider(),
            detector=CountingDetector(),
        )
        record = pipeline.analyze(ORIGIN, DEST)
        classes = {r["evidence_class"] for r in record["routes"]}
        self.assertTrue(classes <= {"stale"}, f"unexpected evidence classes: {classes}")
        # Stale evidence must never justify a recommendation (Rule 9).
        self.assertIsNone(record["comparison"]["recommended_route_id"])

    def test_timings_still_reported_when_imagery_missing(self):
        routes = [_route([_segment(i) for i in range(3)], "rt-miss", "Route 1 via Missing Road")]
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(routes),
            imagery_adapter=MissingImageryProvider(),
            detector=CountingDetector(),
        )
        record = pipeline.analyze(ORIGIN, DEST)
        self.assertIn("timings_ms", record)
        self.assertIn("total_ms", record["timings_ms"])
        self.assertEqual(record["timings_ms"]["detection_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
