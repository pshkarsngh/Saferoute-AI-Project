"""SafeRoute AI — repeat-work caches (PHASE_31).

These tests lock in the property that the performance work added in PHASE_31
never changes an assessment: it only reuses work whose inputs are provably
identical.

1. The optimised corridor de-duplication returns EXACTLY the previous value.
2. A frame whose file identity and detector configuration are unchanged is
   inferred once per process, and two analyses of the same corridor produce
   identical route scores and identifiers.
3. Rewriting the image file invalidates the memo (re-inference).
4. An identical Mapillary segment query is issued once, and a failure is never
   cached as if it were a result.
5. An identical grounded LLM prompt reuses its reply.

All providers/transport are injected: no network, no YOLO, no .env access.
"""

import json
import shutil
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from src.api.pipeline import SafetyAnalysisPipeline
from src.detection.schemas import DetectionStatus, ImageDetectionResult
from src.imagery.interfaces import ImageryProvider
from src.imagery.mapillary_provider import MapillaryImageryProvider
from src.imagery.schemas import ImageRef, ImageryResult, ImageryStatus
from src.llm.explainer import GroundedExplanationService
from src.routing.multi_adapter import _distance_to_polyline_m, corridor_overlap
from src.routing.schemas import (
    Coordinate,
    Route,
    RouteGeometry,
    RouteResponse,
    RouteSegment,
    RoutingStatus,
)

TMP = Path(__file__).resolve().parent.parent.parent / "data" / "imagery" / "_test_repeat_cache"


def _segment(seq: int, coords) -> RouteSegment:
    return RouteSegment(
        segment_id=f"seg-cache-{seq:04d}", route_id="rt-cache", sequence=seq,
        length_m=100.0, duration_s=10.0,
        start_coord=Coordinate(coords[0][1], coords[0][0]),
        end_coord=Coordinate(coords[-1][1], coords[-1][0]),
        geometry=RouteGeometry(coordinates=list(coords)),
    )


class _FileImageryProvider(ImageryProvider):
    """Returns one image per segment pointing at a real file on disk."""

    def __init__(self, file_path: Path):
        self.file_path = file_path

    @property
    def provider_name(self):
        return "file_test"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        now = datetime.now(timezone.utc).isoformat()
        return ImageryResult(
            segment_id=segment.segment_id, status=ImageryStatus.AVAILABLE,
            images=[ImageRef(
                image_id="img-cache", file_path=str(self.file_path),
                source="file_test", licence="CC-BY 4.0", retrieved_at=now)],
            source="file_test", licence="CC-BY 4.0", limitations=[],
        )


class _CountingDetector:
    model_version = "saferoute-yolo11-test"
    pipeline_version = "preprocess-v1"
    imgsz = 640
    conf_threshold = 0.25
    iou_threshold = 0.45
    max_det = 300
    augment = False
    batch = 1
    checkpoint_path = "fake.pt"
    device = "cpu"

    def __init__(self):
        self.inferences = 0

    def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
        from src.detection.schemas import DetectionRecord

        self.inferences += 1
        return ImageDetectionResult(
            model_version=self.model_version, pipeline_version=self.pipeline_version,
            status=DetectionStatus.SUCCESS, image_id=image_id, route_id=route_id,
            segment_id=segment_id, image_width=640, image_height=640, error=None,
            detections=[DetectionRecord(
                model_version=self.model_version, image_id=image_id,
                route_id=route_id, segment_id=segment_id, hazard_class="pothole",
                confidence=0.9, bbox_xyxy=[10.0, 10.0, 50.0, 50.0],
                bbox_norm=[0.01, 0.01, 0.08, 0.08], status="detected")],
            timing_ms={},
        )


class _StaticProvider:
    def __init__(self, routes):
        self._routes = routes

    @property
    def provider_name(self):
        return "static"

    def get_routes(self, request):
        return RouteResponse(
            status=RoutingStatus.OK, provider=self.provider_name,
            routes=list(self._routes), request_id="req-cache",
            retrieved_at=datetime.now(timezone.utc).isoformat(), limitations=[])


class _FakeMapillaryHttp:
    def __init__(self, payload, fail=False):
        self.payload = payload
        self.fail = fail
        self.search_calls = 0

    def get_json(self, url, params):
        self.search_calls += 1
        if self.fail:
            raise RuntimeError("transport down")
        return self.payload

    def download(self, url, dest, token=""):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"\xff\xd8\xff\xe0fake")
        return True


def _mapillary_provider(http, storage: Path) -> MapillaryImageryProvider:
    return MapillaryImageryProvider(token="tok", http=http, storage_dir=storage)


# --------------------------------------------------------------------------- #
class TestCorridorOverlapEquivalence(unittest.TestCase):
    def _previous(self, a, b, tolerance_m=60.0):
        if len(a) < 2 or len(b) < 2:
            return 0.0
        lat_ref = sum(pt[1] for pt in a) / len(a)

        def coverage(source, target):
            if len(source) > 400:
                step = len(source) / 400.0
                source = [source[int(i * step)] for i in range(400)]
            inside = 0
            for pt in source:
                if _distance_to_polyline_m(pt, target, lat_ref) <= tolerance_m:
                    inside += 1
            return inside / len(source)

        return min(coverage(a, b), coverage(b, a))

    def test_matches_previous_formula_exactly(self):
        a = [(77.60 + i * 0.0002, 12.97 + i * 0.0001) for i in range(120)]
        b = [(77.6001 + i * 0.0002, 12.9701 + i * 0.0001) for i in range(110)]
        c = [(77.70 + i * 0.0002, 12.99 + i * 0.0001) for i in range(90)]
        for left, right in ((a, b), (a, c), (b, c)):
            self.assertEqual(
                self._previous(left, right),
                corridor_overlap(left, right),
                "optimised de-duplication changed a route comparison",
            )

    def test_identical_corridor_is_one_and_unrelated_is_zero(self):
        a = [(77.60 + i * 0.0002, 12.97) for i in range(60)]
        self.assertEqual(corridor_overlap(a, list(a)), 1.0)
        far = [(78.60 + i * 0.0002, 13.97) for i in range(60)]
        self.assertEqual(corridor_overlap(a, far), 0.0)

    def test_empty_and_single_point_geometries_score_zero(self):
        self.assertEqual(corridor_overlap([], [(77.6, 12.9)]), 0.0)
        self.assertEqual(corridor_overlap([(77.6, 12.9)], [(77.6, 12.9)]), 0.0)


class TestDetectionMemoAcrossAnalyses(unittest.TestCase):
    def setUp(self):
        TMP.mkdir(parents=True, exist_ok=True)
        self.image = TMP / "frame.jpg"
        self.image.write_bytes(b"\xff\xd8\xff\xe0frame-one")
        coords = [(77.60 + i * 0.001, 12.97) for i in range(3)]
        self.segments = [_segment(i, [c, (c[0] + 0.001, c[1])])
                         for i, c in enumerate(coords)]
        self.route = Route(
            route_id="rt-cache", provider="static", summary="Route 1 via Test Road",
            distance_m=1000.0, duration_s=100.0,
            geometry=RouteGeometry(coordinates=[(77.60, 12.97), (77.61, 12.98)]),
            segments=self.segments, limitations=[])

    def tearDown(self):
        shutil.rmtree(TMP, ignore_errors=True)

    def _pipeline(self, detector):
        return SafetyAnalysisPipeline(
            routing_provider=_StaticProvider([self.route]),
            imagery_adapter=_FileImageryProvider(self.image),
            detector=detector, imagery_workers=2)

    def test_repeat_analysis_reuses_inference_and_keeps_scores(self):
        detector = _CountingDetector()
        pipeline = self._pipeline(detector)

        first = pipeline.analyze(Coordinate(12.97, 77.60), Coordinate(12.98, 77.61))
        second = pipeline.analyze(Coordinate(12.97, 77.60), Coordinate(12.98, 77.61))

        # All three segments share one file => one inference for the whole first
        # analysis, and the second analysis reuses it without new work.
        self.assertEqual(detector.inferences, 1, "identical frames must be inferred once")
        key = lambda rec: [(r["route_id"], r["route_score"], r["status"], r["hazards_total"])
                           for r in rec["routes"]]
        self.assertEqual(key(first), key(second))
        self.assertEqual(first["recommendation"], second["recommendation"])

    def test_rewritten_image_is_reinferred(self):
        detector = _CountingDetector()
        pipeline = self._pipeline(detector)
        pipeline.analyze(Coordinate(12.97, 77.60), Coordinate(12.98, 77.61))
        self.assertEqual(detector.inferences, 1)

        # Different bytes and a different mtime => a genuinely new frame.
        time.sleep(0.01)
        self.image.write_bytes(b"\xff\xd8\xff\xe0frame-two-different")
        pipeline.analyze(Coordinate(12.97, 77.60), Coordinate(12.98, 77.61))
        self.assertEqual(detector.inferences, 2, "a changed frame must be inferred again")


class TestMapillarySearchCache(unittest.TestCase):
    def setUp(self):
        TMP.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(TMP, ignore_errors=True)

    def _payload(self):
        return {"data": [{
            "id": "777",
            "captured_at": int(time.time() * 1000) - 86_400_000,
            "geometry": {"type": "Point", "coordinates": [77.59465, 12.97165]},
            "thumb_1024_url": "https://example.invalid/777.jpg",
        }]}

    def test_identical_segment_query_is_issued_once(self):
        http = _FakeMapillaryHttp(self._payload())
        provider = _mapillary_provider(http, TMP)
        segment = _segment(0, [(77.5946, 12.9716), (77.5956, 12.9726)])

        first = provider.get_imagery_for_segment(segment)
        second = provider.get_imagery_for_segment(segment)

        self.assertEqual(http.search_calls, 1, "identical bbox must reuse the response")
        self.assertEqual(first.status, ImageryStatus.AVAILABLE)
        self.assertEqual([i.image_id for i in first.images], [i.image_id for i in second.images])

    def test_failure_is_never_cached(self):
        http = _FakeMapillaryHttp(self._payload(), fail=True)
        provider = _mapillary_provider(http, TMP)
        segment = _segment(0, [(77.5946, 12.9716), (77.5956, 12.9726)])

        first = provider.get_imagery_for_segment(segment)
        second = provider.get_imagery_for_segment(segment)

        self.assertEqual(first.status, ImageryStatus.INACCESSIBLE)
        self.assertEqual(second.status, ImageryStatus.INACCESSIBLE)
        self.assertEqual(http.search_calls, 2, "a failure must be retried, never cached")


class TestLlmReplyCache(unittest.TestCase):
    def test_identical_prompt_reuses_reply(self):
        calls = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps({"response": '{"explanation": "verified text"}'}).encode("utf-8")

        def _urlopen(req, timeout=None):
            calls.append(req)
            return _Response()

        service = GroundedExplanationService(
            base_url="http://127.0.0.1:9", model="test", enabled=True)
        body = {"model": "test", "prompt": "verified data", "stream": False}

        with mock.patch("urllib.request.urlopen", _urlopen):
            first = service._post_ollama(body)
            second = service._post_ollama(dict(body))

        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1, "an identical prompt must not hit the model twice")

    def test_different_prompt_is_not_reused(self):
        calls = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps({"response": "reply"}).encode("utf-8")

        def _urlopen(req, timeout=None):
            calls.append(req)
            return _Response()

        service = GroundedExplanationService(
            base_url="http://127.0.0.1:9", model="test", enabled=True)
        with mock.patch("urllib.request.urlopen", _urlopen):
            service._post_ollama({"prompt": "a"})
            service._post_ollama({"prompt": "b"})

        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
