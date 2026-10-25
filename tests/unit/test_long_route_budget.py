"""PHASE_33: long-route evidence budget tests.

A route over 100 km is assessed from an evenly-spaced, bounded segment sample
and at most one frame per assessed segment. The skipped segments remain in the
route denominator as explicit unassessed assessments, so coverage can never
look better than it is.
"""

from datetime import datetime, timezone
import unittest

from src.api.pipeline import SafetyAnalysisPipeline
from src.detection.schemas import DetectionStatus, ImageDetectionResult
from src.imagery.interfaces import ImageryProvider
from src.imagery.schemas import ImageRef, ImageryResult, ImageryStatus
from src.routing.schemas import Coordinate, Route, RouteGeometry, RouteSegment


def _segment(seq: int, length_m: float = 200.0, route_id: str = "rt-long-00") -> RouteSegment:
    return RouteSegment(
        segment_id=f"seg-long-{seq:04d}",
        route_id=route_id,
        sequence=seq,
        length_m=length_m,
        duration_s=length_m / 10.0,
        start_coord=Coordinate(12.97, 77.60 + seq * 0.001),
        end_coord=Coordinate(12.98, 77.61 + seq * 0.001),
        geometry=RouteGeometry(
            coordinates=[
                (77.60 + seq * 0.001, 12.97),
                (77.61 + seq * 0.001, 12.98),
            ]
        ),
    )


def _route(segments, route_id: str = "rt-long-00") -> Route:
    return Route(
        route_id=route_id,
        provider="test",
        summary="Long test corridor",
        distance_m=sum(float(s.length_m) for s in segments),
        duration_s=sum(float(s.duration_s) for s in segments),
        geometry=RouteGeometry(coordinates=[(77.60, 12.97), (77.61, 12.98)]),
        segments=list(segments),
        limitations=[],
    )


class CappingImageryProvider(ImageryProvider):
    """Records the cap requested by the pipeline and returns that many frames."""

    supports_max_images = True

    def __init__(self):
        self.calls = []

    @property
    def provider_name(self):
        return "capping_test"

    def get_imagery_for_segment(self, segment, permitted_source=None, max_images=None):
        self.calls.append((segment.segment_id, max_images))
        count = 3 if max_images is None else max(1, int(max_images))
        now = datetime.now(timezone.utc).isoformat()
        return ImageryResult(
            segment_id=segment.segment_id,
            status=ImageryStatus.AVAILABLE,
            images=[
                ImageRef(
                    image_id=f"{segment.segment_id}-img-{i}",
                    file_path=f"{segment.segment_id}-{i}.jpg",
                    source="capping_test",
                    licence="CC-BY 4.0",
                    retrieved_at=now,
                )
                for i in range(count)
            ],
            source="capping_test",
            licence="CC-BY 4.0",
            limitations=[],
        )


class NoHazardDetector:
    model_version = "saferoute-yolo11-test"
    pipeline_version = "preprocess-v1"

    def __init__(self):
        self.calls = []

    def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
        self.calls.append(str(image_input))
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


class _RoutingProvider:
    provider_name = "long_route_test"

    def __init__(self, routes):
        self._routes = list(routes)

    def get_routes(self, request):
        from src.routing.schemas import RouteResponse, RoutingStatus

        return RouteResponse(
            status=RoutingStatus.OK,
            provider=self.provider_name,
            routes=list(self._routes),
            request_id="req-long",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            limitations=[],
        )


ORIGIN = Coordinate(12.90, 77.50)
DESTINATION = Coordinate(13.10, 77.70)


class TestLongRouteBudget(unittest.TestCase):
    def _pipeline(self, route, provider, detector):
        return SafetyAnalysisPipeline(
            routing_provider=_RoutingProvider([route]),
            imagery_adapter=provider,
            detector=detector,
            imagery_workers=4,
            long_route_threshold_m=100_000.0,
            long_route_max_segments=400,
            long_route_max_images_per_segment=1,
        )

    def test_long_route_samples_segments_and_keeps_full_denominator(self):
        route = _route([_segment(i) for i in range(600)])
        provider = CappingImageryProvider()
        detector = NoHazardDetector()
        pipeline = self._pipeline(route, provider, detector)

        record = pipeline.analyze(ORIGIN, DESTINATION)
        result = record["routes"][0]

        self.assertEqual(len(provider.calls), 400)
        self.assertTrue(all(cap == 1 for _, cap in provider.calls))
        self.assertEqual(len(detector.calls), 400)

        self.assertTrue(result["long_route"]["applied"])
        self.assertTrue(result["long_route"]["sampled"])
        self.assertEqual(result["long_route"]["assessed_segments"], 400)
        self.assertEqual(result["long_route"]["total_segments"], 600)
        self.assertEqual(result["long_route"]["max_images_per_segment"], 1)

        # Every skipped segment is still present, explicitly unassessed.
        self.assertEqual(len(result["segment_scores"]), 600)
        scored = [
            s for s in result["segment_scores"]
            if s.get("segment_score") is not None
        ]
        self.assertEqual(len(scored), 400)
        self.assertAlmostEqual(result["assessed_length_fraction"], 400 / 600, places=3)
        self.assertAlmostEqual(result["coverage"]["fraction"], 400 / 600, places=3)
        self.assertEqual(len(result["imagery"]), 600)
        self.assertEqual(result["status"], "partially_assessed")

        joined = " ".join(result["limitations"])
        self.assertIn("Long-route sampling", joined)
        self.assertIn("Long-route imagery budget", joined)

    def test_short_route_is_unchanged(self):
        route = _route([_segment(i) for i in range(50)])
        provider = CappingImageryProvider()
        detector = NoHazardDetector()
        pipeline = self._pipeline(route, provider, detector)

        # 50 * 200 m = 10 km, well below the 100 km threshold.
        result = pipeline._analyze_route(route)

        self.assertEqual(len(provider.calls), 50)
        self.assertTrue(all(cap is None for _, cap in provider.calls))
        self.assertEqual(len(detector.calls), 150)  # 3 images per segment
        self.assertNotIn("long_route", result)
        self.assertAlmostEqual(result["assessed_length_fraction"], 1.0, places=6)
        self.assertEqual(result["status"], "assessed")

    def test_standalone_long_route_uses_budget(self):
        route = _route([_segment(i) for i in range(600)])
        provider = CappingImageryProvider()
        detector = NoHazardDetector()
        pipeline = self._pipeline(route, provider, detector)

        result = pipeline._analyze_route(route)

        self.assertEqual(len(provider.calls), 400)
        self.assertTrue(all(cap == 1 for _, cap in provider.calls))
        self.assertEqual(result["long_route"]["assessed_segments"], 400)
        self.assertEqual(len(result["segment_scores"]), 600)
        self.assertAlmostEqual(result["assessed_length_fraction"], 400 / 600, places=3)


if __name__ == "__main__":
    unittest.main()
