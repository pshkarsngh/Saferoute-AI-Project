"""PHASE_23B focused regression tests — road imagery integrity.

Hermetic (no network, no token, no YOLO checkpoint). Covers:
1. No fabricated geographic coordinates from local sample imagery.
2. Demo imagery is explicitly identified as demo / not geographically matched.
3. Mapillary 401/403 never silently substitutes unrelated imagery.
4. The same image id is counted only once across adjacent segments.
5. True point-to-segment (perpendicular) distance behaviour + edge cases.
6. Partial/missing imagery coverage stays honest (Rule 9).
7. Secrets never appear in settings output, API responses, or logs/messages.

Governing: master_rules.md Rules 8, 9, 13, 14, 20; TRD §9.4, §10; ARCHITECTURE §7, §8.
"""

import json
import math
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from src.api.app import SafeRouteAPI
from src.api.pipeline import SafetyAnalysisPipeline
from src.api.store import AnalysisStore
from src.config.settings import Settings
from src.detection.schemas import DetectionRecord, DetectionStatus, ImageDetectionResult
from src.geocoding.mock_geocoder import MockGeocoder
from src.imagery.adapter import PermittedImageryAdapter
from src.imagery.interfaces import ImageryProvider
from src.imagery.mapillary_provider import MapillaryImageryProvider
from src.imagery.matcher import SegmentImageryMatcher, point_to_segment_distance_m
from src.imagery.schemas import ImageRef, ImageryResult, ImageryStatus
from src.risk.aggregate import deduplicate_adjacent_segment_hazards
from src.risk.engine import DeterministicRiskEngine
from src.risk.schemas import AssessmentStatus, CoverageInfo, SegmentAssessment
from src.routing.schemas import (
    Coordinate,
    Route,
    RouteGeometry,
    RouteSegment,
)
from src.routing.segmentation import haversine_distance_m

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

# The synthetic anchor the previous (defective) adapter used (audit §5.1).
SYNTHETIC_BENGALURU = (77.5946, 12.9716)


def _segment(
    segment_id="seg-t-0000",
    route_id="route-t",
    coords=None,
    length_m=200.0,
):
    coords = coords or [(77.5946, 12.9716), (77.5956, 12.9726)]
    return RouteSegment(
        segment_id=segment_id, route_id=route_id, sequence=0, length_m=length_m,
        duration_s=20.0,
        start_coord=Coordinate(latitude=coords[0][1], longitude=coords[0][0]),
        end_coord=Coordinate(latitude=coords[-1][1], longitude=coords[-1][0]),
        geometry=RouteGeometry(coordinates=coords),
    )


# --------------------------------------------------------------------------- #
# 1 & 2 — no fabricated coordinates / explicit demo mode
# --------------------------------------------------------------------------- #
class TestNoFabricatedCoordinates(unittest.TestCase):
    def test_default_adapter_never_fabricates_geography(self):
        adapter = PermittedImageryAdapter()
        self.assertFalse(adapter.demo_mode)
        # No catalogue entry may carry a synthesized coordinate.
        for cand in adapter._catalogue:
            self.assertIsNone(cand.get("coordinates"))
            self.assertTrue(cand.get("is_demo"))
            self.assertNotEqual(tuple(cand.get("coordinates") or ()), SYNTHETIC_BENGALURU)

    def test_default_adapter_returns_unmatched_for_real_route(self):
        adapter = PermittedImageryAdapter()
        result = adapter.get_imagery_for_segment(_segment(), permitted_source="workspace_dashcam_v1")
        self.assertFalse(result.is_available)
        self.assertEqual(result.images, [])
        self.assertEqual(result.status, ImageryStatus.UNMATCHED)
        self.assertIn("missing_imagery_not_safe", result.limitations)

    def test_demo_mode_labels_imagery_as_demo_and_discloses(self):
        adapter = PermittedImageryAdapter(demo_mode=True)
        result = adapter.get_imagery_for_segment(_segment(), permitted_source="workspace_dashcam_v1")
        self.assertTrue(result.images, "demo mode should surface the labelled sample frames")
        for img in result.images:
            self.assertTrue(img.is_demo)
            self.assertIsNone(img.coordinates)
            self.assertIsNone(img.distance_to_segment_m)
        self.assertIn("demo_imagery_not_geographically_matched", result.limitations)
        self.assertIn("demo_imagery_not_route_evidence", result.limitations)
        self.assertIn("is_demo", result.images[0].to_dict())

    def test_default_and_demo_adapters_differ_on_same_segment(self):
        seg = _segment()
        default = PermittedImageryAdapter().get_imagery_for_segment(seg)
        demo = PermittedImageryAdapter(demo_mode=True).get_imagery_for_segment(seg)
        self.assertFalse(default.is_available)          # honest unmatched
        self.assertTrue(demo.images)                     # explicit demo only
        self.assertTrue(all(i.is_demo for i in demo.images))

    def test_demo_mode_respects_configured_image_cap(self):
        """PHASE_25: demo mode must honour matching.max_images_per_segment.

        Previously the demo path returned the whole archive for every segment,
        multiplying inference work while demo mode is otherwise OFF by default.
        """
        adapter = PermittedImageryAdapter(demo_mode=True)
        cap = adapter.matcher.max_images
        self.assertGreater(cap, 0)
        result = adapter.get_imagery_for_segment(_segment(), permitted_source="workspace_dashcam_v1")
        self.assertTrue(result.images)
        self.assertLessEqual(len(result.images), cap)
        self.assertTrue(all(i.is_demo for i in result.images))


# --------------------------------------------------------------------------- #
# 3 & 7 — Mapillary auth failure honesty + token redaction
# --------------------------------------------------------------------------- #
class _RaisingHttp:
    def __init__(self, exc):
        self.exc = exc
        self.downloads = 0

    def get_json(self, url, params):
        raise self.exc

    def download(self, url, dest, token=""):
        self.downloads += 1
        raise AssertionError("download must not be attempted on auth failure")


class _RecordingFallback(ImageryProvider):
    provider_name = "recording_fallback"

    def __init__(self):
        self.calls = 0

    def get_imagery_for_segment(self, segment, permitted_source=None):
        self.calls += 1
        return ImageryResult(
            segment_id=segment.segment_id, status=ImageryStatus.AVAILABLE,
            images=[ImageRef(image_id="unrelated", file_path="x.jpg",
                             source="workspace_dashcam_v1", licence="CC-BY 4.0",
                             retrieved_at="2026-01-01T00:00:00Z")],
            limitations=[])


def _provider_with_error(exc, token="tok", fallback=None):
    return MapillaryImageryProvider(
        token=token, http=_RaisingHttp(exc),
        storage_dir=Path(tempfile.mkdtemp(prefix="sr_23b_")),
        search_radius_m=25.0, fallback=fallback)


class TestMapillaryAuthFailure(unittest.TestCase):
    def test_401_never_uses_unrelated_fallback(self):
        fallback = _RecordingFallback()
        exc = urllib.error.HTTPError("https://graph.mapillary.com/images", 401,
                                     "Unauthorized", {}, None)
        res = _provider_with_error(exc, fallback=fallback).get_imagery_for_segment(_segment())
        self.assertEqual(res.status, ImageryStatus.INACCESSIBLE)
        self.assertEqual(res.images, [])
        self.assertEqual(fallback.calls, 0, "unrelated fallback imagery must NOT be substituted")
        self.assertIn("mapillary_auth_failed", res.limitations)
        self.assertIn("missing_imagery_not_safe", res.limitations)

    def test_403_never_uses_unrelated_fallback(self):
        fallback = _RecordingFallback()
        exc = urllib.error.HTTPError("https://graph.mapillary.com/images", 403,
                                     "Forbidden", {}, None)
        res = _provider_with_error(exc, fallback=fallback).get_imagery_for_segment(_segment())
        self.assertEqual(res.status, ImageryStatus.INACCESSIBLE)
        self.assertEqual(fallback.calls, 0)

    def test_token_never_leaks_in_error_message(self):
        token = "supersecret-token-xyz"
        exc = RuntimeError(f"request failed for access_token={token}")
        res = _provider_with_error(exc, token=token).get_imagery_for_segment(_segment())
        blob = json.dumps(res.to_dict())
        self.assertNotIn(token, blob)
        self.assertNotIn(token, res.unavailable_detail.message)


# --------------------------------------------------------------------------- #
# 4 — cross-segment de-duplication
# --------------------------------------------------------------------------- #
def _hazard(image_id, hazard_class="pothole", bbox=None, severity=3.0):
    from src.risk.schemas import HazardRecord
    return HazardRecord(
        model_version="saferoute-yolo11-v1", image_id=image_id, hazard_class=hazard_class,
        confidence=0.9, bbox_xyxy=list(bbox or [10.0, 10.0, 60.0, 60.0]),
        bbox_norm=[0.1, 0.1, 0.3, 0.3], severity=severity, status="assessed")


def _asm(segment_id, hazards):
    return SegmentAssessment(
        segment_id=segment_id, model_version="saferoute-yolo11-v1",
        coverage=CoverageInfo(images_total=1, images_used=1, fraction=1.0),
        hazards=list(hazards),
        aggregate_hazard=float(sum(h.severity for h in hazards)),
        status=AssessmentStatus.ASSESSED)


class TestCrossSegmentDeduplication(unittest.TestCase):
    def test_helper_dedups_same_image_hazard_across_segments(self):
        a = _asm("s1", [_hazard("img-shared")])
        b = _asm("s2", [_hazard("img-shared")])
        deduped, count = deduplicate_adjacent_segment_hazards([a, b], 0.50)
        self.assertEqual(count, 1)
        self.assertEqual(len(deduped[0].hazards), 1)   # first occurrence retained
        self.assertEqual(len(deduped[1].hazards), 0)   # duplicate removed
        self.assertEqual(deduped[1].aggregate_hazard, 0.0)
        self.assertTrue(any("cross_segment_duplicate" in lim for lim in deduped[1].limitations))

    def test_helper_preserves_distinct_hazards(self):
        a = _asm("s1", [_hazard("img-shared", bbox=[10, 10, 60, 60])])
        b = _asm("s2", [_hazard("img-shared", bbox=[200, 200, 260, 260])])  # different pothole
        d2 = _asm("s3", [_hazard("other-img")])
        deduped, count = deduplicate_adjacent_segment_hazards([a, b, d2], 0.50)
        self.assertEqual(count, 0)
        self.assertEqual(len(deduped[1].hazards), 1)
        self.assertEqual(len(deduped[2].hazards), 1)

    def test_helper_keeps_hazards_without_image_identity(self):
        a = _asm("s1", [_hazard(None)])
        b = _asm("s2", [_hazard(None)])
        deduped, count = deduplicate_adjacent_segment_hazards([a, b], 0.50)
        self.assertEqual(count, 0)
        self.assertEqual(len(deduped[0].hazards), 1)
        self.assertEqual(len(deduped[1].hazards), 1)

    def test_engine_route_counts_shared_image_once(self):
        engine = DeterministicRiskEngine()
        self.assertTrue(engine.dedup_adjacent_segments)
        route = engine.score_route("r", [_asm("s1", [_hazard("img-shared")]),
                                         _asm("s2", [_hazard("img-shared")])],
                                   [200.0, 200.0])
        self.assertEqual(route.hazards_total, 1)

    def test_pipeline_counts_shared_image_once(self):
        class _SharedImageProvider(ImageryProvider):
            provider_name = "shared_image"

            def get_imagery_for_segment(self, segment, permitted_source=None):
                now = datetime.now(timezone.utc).isoformat()
                return ImageryResult(
                    segment_id=segment.segment_id, status=ImageryStatus.AVAILABLE,
                    images=[ImageRef(image_id="shared-img-1", file_path="shared.jpg",
                                     source="workspace_dashcam_v1", licence="CC-BY 4.0",
                                     retrieved_at=now)],
                    source="workspace_dashcam_v1", licence="CC-BY 4.0")

        class _OneHazardDetector:
            model_version = "saferoute-yolo11-v1"
            pipeline_version = "preprocess-v1"

            def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
                return ImageDetectionResult(
                    model_version=self.model_version, pipeline_version=self.pipeline_version,
                    status=DetectionStatus.SUCCESS, image_id=image_id, route_id=route_id,
                    segment_id=segment_id,
                    detections=[DetectionRecord(
                        model_version=self.model_version, image_id=image_id, route_id=route_id,
                        segment_id=segment_id, hazard_class="pothole", confidence=0.9,
                        bbox_xyxy=[10.0, 10.0, 60.0, 60.0], bbox_norm=[0.1, 0.1, 0.3, 0.3])])

        pipeline = SafetyAnalysisPipeline(
            imagery_adapter=_SharedImageProvider(), detector=_OneHazardDetector())

        seg1 = _segment("seg-r-0000", "r", [(77.5946, 12.9716), (77.5956, 12.9726)])
        seg2 = _segment("seg-r-0001", "r", [(77.5956, 12.9726), (77.5966, 12.9736)])
        route = Route(route_id="r", provider="test", summary="s", distance_m=400.0,
                      duration_s=40.0,
                      geometry=RouteGeometry(coordinates=[(77.5946, 12.9716), (77.5966, 12.9736)]),
                      segments=[seg1, seg2])

        result = pipeline._analyze_route(route)
        self.assertEqual(result["hazards_total"], 1)
        self.assertEqual(len(result["hazards"]), 1)


# --------------------------------------------------------------------------- #
# 5 — point-to-segment distance
# --------------------------------------------------------------------------- #
class TestPointToSegmentDistance(unittest.TestCase):
    # ~1113 m straight segment along the equator.
    LONG_LINE = [(0.0, 0.0), (0.01, 0.0)]

    def test_point_on_middle_of_long_segment_matches(self):
        d = point_to_segment_distance_m((0.005, 0.0001), self.LONG_LINE)
        self.assertLess(d, 25.0)
        # A vertex-only implementation would have returned ~550 m here.
        self.assertLess(d, 15.0)

    def test_point_on_the_line_is_near_zero(self):
        self.assertLess(point_to_segment_distance_m((0.005, 0.0), self.LONG_LINE), 1.0)

    def test_point_outside_radius_is_rejected(self):
        d = point_to_segment_distance_m((0.005, 0.001), self.LONG_LINE)  # ~111 m
        self.assertGreater(d, 25.0)

    def test_matcher_uses_perpendicular_distance(self):
        matcher = SegmentImageryMatcher(search_radius_meters=25.0)
        seg = RouteSegment(
            segment_id="seg-mid", route_id="r", sequence=0, length_m=1113.0, duration_s=60.0,
            start_coord=Coordinate(0.0, 0.0), end_coord=Coordinate(0.0, 0.01),
            geometry=RouteGeometry(coordinates=self.LONG_LINE))

        candidates = [
            {"image_id": "middle", "coordinates": (0.005, 0.0001)},  # ~11 m off, mid-edge
            {"image_id": "far", "coordinates": (0.005, 0.001)},      # ~111 m off
        ]
        matches = matcher.match_candidates(seg, candidates)
        ids = [c["image_id"] for c, _ in matches]
        self.assertIn("middle", ids)
        self.assertNotIn("far", ids)

    def test_edge_cases(self):
        self.assertEqual(point_to_segment_distance_m((1.0, 1.0), []), float("inf"))
        single = point_to_segment_distance_m((1.0, 1.0), [(0.0, 0.0)])
        self.assertAlmostEqual(single, haversine_distance_m((1.0, 1.0), (0.0, 0.0)), places=6)
        # Degenerate (coincident vertices) must not raise / divide by zero.
        degenerate = point_to_segment_distance_m((0.001, 0.001), [(0.0, 0.0), (0.0, 0.0)])
        self.assertTrue(math.isfinite(degenerate))
        self.assertGreater(degenerate, 0.0)


# --------------------------------------------------------------------------- #
# 6 — coverage honesty preserved
# --------------------------------------------------------------------------- #
class TestCoverageHonesty(unittest.TestCase):
    def test_partial_coverage_never_scores_missing_segment(self):
        engine = DeterministicRiskEngine()
        covered = SegmentAssessment(
            segment_id="s1", model_version="saferoute-yolo11-v1",
            coverage=CoverageInfo(images_total=2, images_used=2, fraction=1.0),
            hazards=[], aggregate_hazard=0.0, status=AssessmentStatus.ASSESSED)
        missing = SegmentAssessment(
            segment_id="s2", model_version="saferoute-yolo11-v1",
            coverage=CoverageInfo(images_total=0, images_used=0, fraction=0.0),
            hazards=[], aggregate_hazard=0.0, status=AssessmentStatus.UNASSESSED)
        route = engine.score_route("r", [covered, missing], [400.0, 600.0])
        self.assertEqual(route.detection_outcome, "insufficient_coverage")
        self.assertIsNone(route.segment_scores[1].segment_score)
        self.assertTrue(route.segment_scores[1].is_suppressed)


# --------------------------------------------------------------------------- #
# 7 — secrets never leak
# --------------------------------------------------------------------------- #
class TestSecretHygiene(unittest.TestCase):
    TOKEN = "mapillary-secret-token-abc123"

    def setUp(self):
        self.db = Path("data/test_phase23b.db")
        if self.db.exists():
            self.db.unlink()

    def tearDown(self):
        if self.db.exists():
            self.db.unlink()

    def test_settings_never_serialise_token(self):
        s = Settings(mapillary_token=self.TOKEN)
        self.assertNotIn(self.TOKEN, json.dumps(s.to_safe_dict()))
        self.assertNotIn(self.TOKEN, repr(s))

    def test_api_responses_never_contain_token(self):
        from tests.unit.test_api import AllMissingImageryProvider, FakeDetector
        s = Settings(mapillary_token=self.TOKEN)
        api = SafeRouteAPI(
            pipeline=SafetyAnalysisPipeline(imagery_adapter=AllMissingImageryProvider(),
                                              detector=FakeDetector()),
            store=AnalysisStore(db_path=self.db), settings=s, geocoder=MockGeocoder())
        self.assertNotIn(self.TOKEN, json.dumps(api.health()[1]))
        self.assertNotIn(self.TOKEN, json.dumps(api.config()[1]))


if __name__ == "__main__":
    unittest.main()
