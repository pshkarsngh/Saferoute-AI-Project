"""Tests for concurrent (parallel) imagery prefetch in the analysis pipeline.

PHASE_26 changed ONLY the I/O schedule of imagery retrieval: segments are
fetched concurrently but consumed in their original order. These tests prove
that the parallel path is behaviourally identical to the sequential path
(Rules 7, 9, 10) and that errors still surface deterministically.
"""

import threading
import time
import unittest
from datetime import datetime, timezone

from src.api.pipeline import SafetyAnalysisPipeline
from src.detection.schemas import DetectionStatus, ImageDetectionResult
from src.imagery.interfaces import ImageryProvider
from src.imagery.schemas import ImageRef, ImageryResult, ImageryStatus
from src.routing.schemas import Coordinate, RouteGeometry, RouteSegment


def _segment(seq: int) -> RouteSegment:
    return RouteSegment(
        segment_id=f"seg-test-{seq:04d}",
        route_id="rt-test-00",
        sequence=seq,
        length_m=100.0,
        duration_s=10.0,
        start_coord=Coordinate(12.97, 77.60 + seq * 0.001),
        end_coord=Coordinate(12.98, 77.61 + seq * 0.001),
        geometry=RouteGeometry(coordinates=[(77.60 + seq * 0.001, 12.97), (77.61 + seq * 0.001, 12.98)]),
    )


class OrderedImageryProvider(ImageryProvider):
    """Returns one image per segment, tagging the image id with the segment seq.

    Records call order and can inject a per-segment delay so the pool genuinely
    interleaves its work.
    """

    def __init__(self, delay: float = 0.0, fail_on: int | None = None):
        self.delay = delay
        self.fail_on = fail_on
        self.call_order: list[int] = []
        self.lock = threading.Lock()

    @property
    def provider_name(self):
        return "ordered_test"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        seq = int(segment.segment_id.rsplit("-", 1)[-1])
        with self.lock:
            self.call_order.append(seq)
        if self.delay:
            time.sleep(self.delay)
        if self.fail_on is not None and seq == self.fail_on:
            raise RuntimeError(f"boom on segment {seq}")
        now = datetime.now(timezone.utc).isoformat()
        return ImageryResult(
            segment_id=segment.segment_id,
            status=ImageryStatus.AVAILABLE,
            images=[ImageRef(
                image_id=f"img-{seq}", file_path=f"{seq}.jpg", source="ordered_test",
                licence="CC-BY 4.0", retrieved_at=now)],
            source="ordered_test", licence="CC-BY 4.0", limitations=[],
        )


class _FakeDetector:
    """Records detection calls so ordering can be asserted."""

    model_version = "saferoute-yolo11-test"
    pipeline_version = "preprocess-v1"

    def __init__(self):
        self.calls: list[int] = []

    def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
        seq = int(str(image_input).split(".")[0])
        self.calls.append(seq)
        return ImageDetectionResult(
            model_version=self.model_version, pipeline_version=self.pipeline_version,
            status=DetectionStatus.NO_DETECTIONS, image_id=image_id,
            route_id=route_id, segment_id=segment_id, detections=[],
            image_width=640, image_height=640, error=None, timing_ms={},
        )


def _route(segments, route_id="rt-test-00", summary="Route 1 via Test Road"):
    from src.routing.schemas import Route

    return Route(
        route_id=route_id, provider="test", summary=summary,
        distance_m=1000.0, duration_s=100.0,
        geometry=RouteGeometry(coordinates=[(77.60, 12.97), (77.61, 12.98)]),
        segments=list(segments), limitations=[],
    )


class MultiRouteProvider:
    """Routing provider that returns a caller-supplied set of distinct routes.

    Used to prove the pipeline requests, analyses and preserves EVERY route the
    provider returns (Rule 10: never more, never fewer, never fabricated).
    """

    def __init__(self, routes):
        self._routes = list(routes)

    @property
    def provider_name(self):
        return "multi_route_test"

    def get_routes(self, request):
        from src.routing.schemas import RouteResponse, RoutingStatus

        return RouteResponse(
            status=RoutingStatus.OK, provider=self.provider_name,
            routes=list(self._routes), request_id="req-test",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            limitations=["fewer_than_four_routes_returned"] if len(self._routes) < 4 else [],
        )


class TestParallelImageryPrefetch(unittest.TestCase):
    def test_results_match_sequential_order(self):
        segments = [_segment(i) for i in range(12)]
        seq_provider = OrderedImageryProvider()
        par_provider = OrderedImageryProvider()

        seq_pipeline = SafetyAnalysisPipeline(
            imagery_adapter=seq_provider, detector=_FakeDetector(), imagery_workers=1)
        par_pipeline = SafetyAnalysisPipeline(
            imagery_adapter=par_provider, detector=_FakeDetector(), imagery_workers=6)

        seq_result = seq_pipeline._analyze_route(_route(segments))
        par_result = par_pipeline._analyze_route(_route(segments))

        # Identical assessment outcome irrespective of I/O schedule.
        self.assertEqual(seq_result["route_score"], par_result["route_score"])
        self.assertEqual(seq_result["status"], par_result["status"])
        self.assertEqual(
            [s["segment_id"] for s in seq_result["segment_scores"]],
            [s["segment_id"] for s in par_result["segment_scores"]],
        )
        self.assertEqual(
            [i["segment_id"] for i in seq_result["imagery"]],
            [i["segment_id"] for i in par_result["imagery"]],
        )

    def test_parallel_actually_overlaps(self):
        """With a per-segment delay, concurrency must beat sequential wall time."""
        segments = [_segment(i) for i in range(8)]
        delay = 0.05

        seq_pipeline = SafetyAnalysisPipeline(
            imagery_adapter=OrderedImageryProvider(delay=delay),
            detector=_FakeDetector(), imagery_workers=1)
        par_pipeline = SafetyAnalysisPipeline(
            imagery_adapter=OrderedImageryProvider(delay=delay),
            detector=_FakeDetector(), imagery_workers=8)

        t0 = time.perf_counter()
        seq_pipeline._analyze_route(_route(segments))
        seq_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        par_pipeline._analyze_route(_route(segments))
        par_time = time.perf_counter() - t0

        self.assertLess(par_time, seq_time * 0.75,
                        f"parallel={par_time:.3f}s not clearly faster than sequential={seq_time:.3f}s")

    def test_detection_runs_in_segment_order_under_concurrency(self):
        segments = [_segment(i) for i in range(10)]
        detector = _FakeDetector()
        pipeline = SafetyAnalysisPipeline(
            imagery_adapter=OrderedImageryProvider(delay=0.01),
            detector=detector, imagery_workers=5)
        pipeline._analyze_route(_route(segments))
        self.assertEqual(detector.calls, list(range(10)))

    def test_provider_error_still_surfaces(self):
        segments = [_segment(i) for i in range(6)]
        pipeline = SafetyAnalysisPipeline(
            imagery_adapter=OrderedImageryProvider(fail_on=3),
            detector=_FakeDetector(), imagery_workers=4)
        with self.assertRaises(RuntimeError):
            pipeline._analyze_route(_route(segments))

    def test_single_segment_uses_sequential_path(self):
        pipeline = SafetyAnalysisPipeline(
            imagery_adapter=OrderedImageryProvider(),
            detector=_FakeDetector(), imagery_workers=8)
        result = pipeline._analyze_route(_route([_segment(0)]))
        self.assertEqual(result["status"], "assessed")
        self.assertEqual(len(result["imagery"]), 1)

    def test_worker_count_configuration(self):
        self.assertEqual(SafetyAnalysisPipeline(imagery_workers=1).imagery_workers, 1)
        self.assertEqual(SafetyAnalysisPipeline(imagery_workers=0).imagery_workers, 1)
        self.assertEqual(SafetyAnalysisPipeline(imagery_workers=16).imagery_workers, 16)


class TestMultipleRoutesThroughParallelPipeline(unittest.TestCase):
    """Every distinct route the provider returns is analysed and preserved."""

    def _routes(self):
        r1 = _route([_segment(i) for i in range(5)], route_id="rt-a", summary="Route 1 via A Road")
        r2 = _route([_segment(i) for i in range(5, 11)], route_id="rt-b", summary="Route 2 via B Road")
        return [r1, r2]

    def test_both_routes_are_analysed_and_ordered(self):
        provider = MultiRouteProvider(self._routes())
        pipeline = SafetyAnalysisPipeline(
            routing_provider=provider, imagery_adapter=OrderedImageryProvider(),
            detector=_FakeDetector(), imagery_workers=4)

        record = pipeline.analyze(Coordinate(12.97, 77.60), Coordinate(12.98, 77.61))

        self.assertEqual(len(record["routes"]), 2, "pipeline must not drop returned routes")
        self.assertEqual([r["route_id"] for r in record["routes"]], ["rt-a", "rt-b"])
        # Comparison ranks exactly the routes returned by the provider.
        ranking_ids = [e["route_id"] for e in record["comparison"]["ranking"]]
        self.assertEqual(sorted(ranking_ids), ["rt-a", "rt-b"])
        self.assertEqual(record["recommendation"], record["comparison"]["recommended_route_id"])

    def test_multi_route_parallel_matches_sequential(self):
        seq_pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(self._routes()),
            imagery_adapter=OrderedImageryProvider(), detector=_FakeDetector(), imagery_workers=1)
        par_pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(self._routes()),
            imagery_adapter=OrderedImageryProvider(), detector=_FakeDetector(), imagery_workers=8)

        seq = seq_pipeline.analyze(Coordinate(12.97, 77.60), Coordinate(12.98, 77.61))
        par = par_pipeline.analyze(Coordinate(12.97, 77.60), Coordinate(12.98, 77.61))

        self.assertEqual(
            [(r["route_id"], r["route_score"], r["status"]) for r in seq["routes"]],
            [(r["route_id"], r["route_score"], r["status"]) for r in par["routes"]],
        )
        self.assertEqual(seq["recommendation"], par["recommendation"])
        self.assertEqual(seq["status"], par["status"])

    def test_single_route_provider_limitation_is_disclosed(self):
        routes = [_route([_segment(i) for i in range(4)], route_id="rt-solo")]
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(routes),
            imagery_adapter=OrderedImageryProvider(), detector=_FakeDetector(), imagery_workers=4)

        record = pipeline.analyze(Coordinate(12.97, 77.60), Coordinate(12.98, 77.61))

        # Exactly one route, never padded to look like more.
        self.assertEqual(len(record["routes"]), 1)
        self.assertIn("fewer_than_four_routes_returned", record["limitations"])

    def test_slow_imagery_provider_completes_and_overlaps_routes(self):
        """A slow provider must still finish, and cross-route prefetch must overlap.

        Both routes' imagery is fetched in one pool, so total imagery wall time
        stays close to a single route's rather than doubling.
        """
        delay = 0.05
        per_route_segments = 6
        routes = [
            _route([_segment(i) for i in range(per_route_segments)], route_id="rt-slow-1"),
            _route([_segment(i) for i in range(per_route_segments, per_route_segments * 2)],
                   route_id="rt-slow-2"),
        ]
        pipeline = SafetyAnalysisPipeline(
            routing_provider=MultiRouteProvider(routes),
            imagery_adapter=OrderedImageryProvider(delay=delay),
            detector=_FakeDetector(), imagery_workers=12)

        t0 = time.perf_counter()
        record = pipeline.analyze(Coordinate(12.97, 77.60), Coordinate(12.98, 77.61))
        elapsed = time.perf_counter() - t0

        self.assertEqual(len(record["routes"]), 2)
        # Fully sequential would be 12 * 0.05 = 0.6s. Allow generous headroom yet
        # require clear overlap.
        self.assertLess(elapsed, 12 * delay * 0.6,
                        f"slow multi-route analysis took {elapsed:.3f}s — not overlapping")


if __name__ == "__main__":
    unittest.main()
