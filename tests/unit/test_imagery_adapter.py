"""SafeRoute AI — Unit Tests for Permitted Imagery Acquisition Adapter.

Phase ID: PHASE_14
Follows TRD §10, ARCHITECTURE §8, master_rules.md Rules 1, 8, 9, 14.
"""

from datetime import datetime, timezone, timedelta
import unittest
from pathlib import Path

from src.imagery.schemas import (
    ImageRef,
    ImageryResult,
    ImageryStatus,
    ImageryUnavailable,
)
from src.imagery.interfaces import ImageryProvider
from src.imagery.staleness import StalenessEvaluator
from src.imagery.matcher import (
    SegmentImageryMatcher,
    point_to_segment_distance_m,
)
from src.imagery.adapter import PermittedImageryAdapter
from src.routing.schemas import Coordinate, RouteGeometry, RouteSegment

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPermittedImageryAdapter(unittest.TestCase):
    """Unit test suite verifying permitted sources, staleness, spatial matching, and unavailable handling."""

    def setUp(self):
        self.adapter = PermittedImageryAdapter()
        # Create a test segment centered around Bangalore
        self.segment = RouteSegment(
            segment_id="seg_test_001",
            route_id="route_test",
            sequence=0,
            length_m=200.0,
            duration_s=20.0,
            start_coord=Coordinate(latitude=12.9716, longitude=77.5946),
            end_coord=Coordinate(latitude=12.9726, longitude=77.5956),
            geometry=RouteGeometry(coordinates=[(77.5946, 12.9716), (77.5956, 12.9726)]),
            road_name="Test Avenue",
        )

    def test_rule_8_permitted_sources_verification(self):
        """Rule 8: Only approved open sources are allowed; proprietary/unpermitted sources are rejected."""
        # 1. Workspace dashcam archive (CC-BY 4.0)
        is_ok, licence, _ = self.adapter.is_source_permitted("workspace_dashcam_v1")
        self.assertTrue(is_ok)
        self.assertEqual(licence, "CC-BY 4.0")

        # 2. Mapillary (CC-BY-SA 4.0)
        is_ok, licence, _ = self.adapter.is_source_permitted("mapillary")
        self.assertTrue(is_ok)
        self.assertEqual(licence, "CC-BY-SA 4.0")

        # 3. Disallowed Google Street View
        is_ok, licence, reason = self.adapter.is_source_permitted("google_street_view")
        self.assertFalse(is_ok)
        self.assertIn("forbids", reason.lower())

        # 4. Completely unknown source
        is_ok, _, _ = self.adapter.is_source_permitted("unauthorized_camera_scrape")
        self.assertFalse(is_ok)

    def test_rule_8_rejection_of_disallowed_source_query(self):
        """Attempting to acquire imagery from disallowed source returns DISALLOWED_SOURCE (Rule 8)."""
        result = self.adapter.get_imagery_for_segment(self.segment, permitted_source="google_street_view")
        self.assertEqual(result.status, ImageryStatus.DISALLOWED_SOURCE)
        self.assertFalse(result.is_available)
        self.assertEqual(len(result.images), 0)
        self.assertIsNotNone(result.unavailable_detail)
        self.assertIn("missing_imagery_not_safe", result.limitations)

    def test_successful_imagery_matching_and_provenance(self):
        """Matching segment within 25m buffer acquires valid ImageRef with full provenance."""
        # Isolate catalog with a fresh candidate
        self.adapter._catalogue = []
        now_utc = datetime.now(timezone.utc)
        fresh_date = (now_utc - timedelta(days=30)).isoformat()

        candidate = {
            "image_id": "frame_fresh_01",
            "file_path": str(WORKSPACE_ROOT / "data" / "imagery" / "frame_fresh_01.jpg"),
            "source": "workspace_dashcam_v1",
            "coordinates": (77.5946, 12.9716),  # Exactly matches start_coord
            "captured_at": fresh_date,
        }
        self.adapter.register_candidate_images([candidate])

        result = self.adapter.get_imagery_for_segment(self.segment, permitted_source="workspace_dashcam_v1")
        self.assertTrue(result.is_available)
        self.assertEqual(result.status, ImageryStatus.AVAILABLE)
        self.assertGreaterEqual(len(result.images), 1)

        first_img = result.images[0]
        self.assertEqual(first_img.licence, "CC-BY 4.0")
        self.assertEqual(first_img.source, "workspace_dashcam_v1")
        self.assertFalse(first_img.is_stale)
        self.assertIsNotNone(first_img.retrieved_at)
        self.assertLessEqual(first_img.distance_to_segment_m, 5.0)

    def test_rule_9_unmatched_segment_yields_unavailable(self):
        """Segment with no imagery within 25m buffer returns UNMATCHED and never assumes safety."""
        # Query a segment in London (far away from Bangalore coordinates)
        london_segment = RouteSegment(
            segment_id="seg_london_01",
            route_id="route_london",
            sequence=0,
            length_m=300.0,
            duration_s=25.0,
            start_coord=Coordinate(latitude=51.5074, longitude=-0.1278),
            end_coord=Coordinate(latitude=51.5084, longitude=-0.1268),
            geometry=RouteGeometry(coordinates=[(-0.1278, 51.5074), (-0.1268, 51.5084)]),
        )

        result = self.adapter.get_imagery_for_segment(london_segment, permitted_source="workspace_dashcam_v1")
        self.assertEqual(result.status, ImageryStatus.UNMATCHED)
        self.assertFalse(result.is_available)
        self.assertEqual(len(result.images), 0)
        self.assertIsNotNone(result.unavailable_detail)
        self.assertIn("missing_imagery_not_safe", result.limitations)

    def test_staleness_evaluator_flagging(self):
        """Rule 9: Imagery older than 180 days is flagged as stale with disclosure limitation."""
        evaluator = StalenessEvaluator(max_age_days=180)
        ref_time = datetime(2026, 10, 13, tzinfo=timezone.utc)

        # Fresh image: ~60 days old
        fresh_ts = "2026-08-14T10:00:00Z"
        is_stale, age, note = evaluator.evaluate(fresh_ts, reference_time=ref_time)
        self.assertFalse(is_stale)
        self.assertAlmostEqual(age, 60, delta=1)
        self.assertIsNone(note)

        # Stale image: ~300 days old
        stale_ts = "2025-12-17T10:00:00Z"
        is_stale, age, note = evaluator.evaluate(stale_ts, reference_time=ref_time)
        self.assertTrue(is_stale)
        self.assertAlmostEqual(age, 300, delta=1)
        self.assertIn("stale", note.lower())

        # Unknown timestamp
        is_stale, _, note = evaluator.evaluate(None, reference_time=ref_time)
        self.assertTrue(is_stale)
        self.assertIn("unrecorded", note.lower())

    def test_spatial_matcher_buffer_exclusion(self):
        """Candidates beyond 25m radius must be excluded by matcher."""
        matcher = SegmentImageryMatcher(search_radius_meters=25.0)

        # Line coordinates near (77.0, 12.0)
        line = [(77.0000, 12.0000), (77.0010, 12.0000)]
        seg = RouteSegment(
            segment_id="seg_m",
            route_id="rt_m",
            sequence=0,
            length_m=100.0,
            duration_s=10.0,
            start_coord=Coordinate(latitude=12.0000, longitude=77.0000),
            end_coord=Coordinate(latitude=12.0000, longitude=77.0010),
            geometry=RouteGeometry(coordinates=line),
        )

        candidates = [
            {"image_id": "near", "coordinates": (77.0001, 12.00005)},   # ~6 meters away
            {"image_id": "far", "coordinates": (77.0050, 12.0050)},     # ~700 meters away
        ]

        matches = matcher.match_candidates(seg, candidates)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0]["image_id"], "near")
        self.assertLess(matches[0][1], 25.0)

    def test_workspace_isolation_storage_path(self):
        """Rule 1: Storage directory must be located strictly inside the workspace."""
        self.assertTrue(str(self.adapter.storage_dir).startswith(str(WORKSPACE_ROOT)))

    def test_serialization_contracts(self):
        """Schemas serialize properly to JSON-compatible dictionaries."""
        ref = ImageRef(
            image_id="img_123",
            file_path="data/imagery/img_123.jpg",
            source="workspace_dashcam_v1",
            licence="CC-BY 4.0",
            retrieved_at="2026-10-13T22:00:00Z",
            captured_at="2026-09-01T12:00:00Z",
            coordinates=(77.5946, 12.9716),
            distance_to_segment_m=4.2,
            is_stale=False,
            status="available",
        )
        d = ref.to_dict()
        self.assertEqual(d["image_id"], "img_123")
        self.assertEqual(d["distance_to_segment_m"], 4.2)
        self.assertFalse(d["is_stale"])


if __name__ == "__main__":
    unittest.main()
