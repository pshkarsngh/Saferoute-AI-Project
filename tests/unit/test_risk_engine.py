"""SafeRoute AI — Unit Tests for Deterministic Risk Engine.

Phase ID: PHASE_12
Follows TRD §9, ARCHITECTURE §7, master_rules.md Rules 7, 9, 11, 12, 17.
"""

import math
import unittest
from pathlib import Path

from src.risk.engine import DeterministicRiskEngine, compute_config_hash
from src.risk.schemas import (
    AssessmentStatus,
    CoverageInfo,
    HazardRecord,
    SegmentAssessment,
    SegmentScoreResult,
    RouteSafetyResult,
)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


class TestDeterministicRiskEngine(unittest.TestCase):
    """Unit test suite verifying deterministic scoring, decay formulas, coverage policies, and hash traceability."""

    def setUp(self):
        self.config_path = WORKSPACE_ROOT / "config" / "risk_engine.yaml"
        self.engine = DeterministicRiskEngine(config_path=self.config_path)

    def test_pure_function_determinism(self):
        """Rule 7: Identical inputs must yield identical outputs across multiple invocations."""
        cov = CoverageInfo(images_total=10, images_used=10, fraction=1.0)
        asm = SegmentAssessment(
            segment_id="seg_det",
            model_version="saferoute-yolo11-v1",
            coverage=cov,
            aggregate_hazard=6.0,
            status=AssessmentStatus.ASSESSED,
        )

        res1 = self.engine.score_segment(asm, length_m=500.0)
        res2 = self.engine.score_segment(asm, length_m=500.0)

        self.assertEqual(res1.segment_score, res2.segment_score)
        self.assertEqual(res1.hazard_density_H, res2.hazard_density_H)
        self.assertEqual(res1.to_dict(), res2.to_dict())

        # Test route determinism
        route1 = self.engine.score_route("rt_det", [asm], [500.0])
        route2 = self.engine.score_route("rt_det", [asm], [500.0])
        self.assertEqual(route1.to_dict(), route2.to_dict())

    def test_candidate_formula_zero_hazard_is_perfect(self):
        """Verify H_i = 0 yields S_i = 100.0."""
        cov = CoverageInfo(images_total=5, images_used=5, fraction=1.0)
        asm = SegmentAssessment(
            segment_id="seg_clean",
            model_version="saferoute-yolo11-v1",
            coverage=cov,
            aggregate_hazard=0.0,
            status=AssessmentStatus.ASSESSED,
        )

        result = self.engine.score_segment(asm, length_m=1000.0)
        self.assertEqual(result.hazard_density_H, 0.0)
        self.assertEqual(result.segment_score, 100.0)
        self.assertFalse(result.is_suppressed)

    def test_candidate_formula_monotonic_decay(self):
        """Verify safety score decays strictly monotonically as hazard increases."""
        cov = CoverageInfo(images_total=5, images_used=5, fraction=1.0)
        scores = []
        for hazard in [0.0, 3.0, 6.0, 15.0, 50.0, 200.0]:
            asm = SegmentAssessment(
                segment_id=f"seg_h_{hazard}",
                model_version="saferoute-yolo11-v1",
                coverage=cov,
                aggregate_hazard=hazard,
                status=AssessmentStatus.ASSESSED,
            )
            res = self.engine.score_segment(asm, length_m=1000.0)
            scores.append(res.segment_score)
            self.assertGreaterEqual(res.segment_score, 0.0)
            self.assertLessEqual(res.segment_score, 100.0)

        # Strictly decreasing
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i], scores[i + 1])

        # Large hazard approaches 0.0
        self.assertLess(scores[-1], 1.0)

    def test_hazard_density_length_normalization(self):
        """Verify H_i = sum(severities) / length_km, with 100m minimum baseline."""
        cov = CoverageInfo(images_total=5, images_used=5, fraction=1.0)
        # 1 km road with aggregate hazard 5.0 -> density 5.0
        asm1 = SegmentAssessment(
            segment_id="seg_1km",
            model_version="saferoute-yolo11-v1",
            coverage=cov,
            aggregate_hazard=5.0,
            status=AssessmentStatus.ASSESSED,
        )
        res1 = self.engine.score_segment(asm1, length_m=1000.0)
        self.assertAlmostEqual(res1.hazard_density_H, 5.0, places=3)

        # 500m road with aggregate hazard 5.0 -> density 10.0
        res2 = self.engine.score_segment(asm1, length_m=500.0)
        self.assertAlmostEqual(res2.hazard_density_H, 10.0, places=3)

        # 50m road (below 100m clamp) with aggregate hazard 5.0 -> clamped to 0.1km -> density 50.0
        res3 = self.engine.score_segment(asm1, length_m=50.0)
        self.assertAlmostEqual(res3.hazard_density_H, 50.0, places=3)

    def test_rule_9_missing_imagery_is_never_zero_risk(self):
        """Rule 9: Missing road imagery must not yield safe scores (score is None, suppressed)."""
        empty_cov = CoverageInfo(images_total=0, images_used=0, fraction=0.0)
        asm_unassessed = SegmentAssessment(
            segment_id="seg_no_img",
            model_version="saferoute-yolo11-v1",
            coverage=empty_cov,
            aggregate_hazard=0.0,  # Even if 0 hazards detected!
            status=AssessmentStatus.UNASSESSED,
        )

        res = self.engine.score_segment(asm_unassessed, length_m=500.0)
        self.assertIsNone(res.segment_score)
        self.assertIsNone(res.hazard_density_H)
        self.assertEqual(res.status, AssessmentStatus.UNASSESSED)
        self.assertTrue(res.is_suppressed)
        self.assertTrue(any("Missing road imagery" in lim for lim in res.limitations))

    def test_rule_9_failed_imagery_handling(self):
        """Segments with pipeline/decode failure must produce None score and suppressed flag."""
        failed_cov = CoverageInfo(images_total=5, images_used=0, fraction=0.0)
        asm_failed = SegmentAssessment(
            segment_id="seg_failed",
            model_version="saferoute-yolo11-v1",
            coverage=failed_cov,
            aggregate_hazard=0.0,
            status=AssessmentStatus.FAILED,
        )

        res = self.engine.score_segment(asm_failed, length_m=500.0)
        self.assertIsNone(res.segment_score)
        self.assertEqual(res.status, AssessmentStatus.FAILED)
        self.assertTrue(res.is_suppressed)
        self.assertTrue(any("failed" in lim for lim in res.limitations))

    def test_rule_9_insufficient_coverage_suppresses_safe_verdict(self):
        """Coverage below 50% must trigger is_suppressed and log a limitation."""
        low_cov = CoverageInfo(images_total=10, images_used=4, fraction=0.40)
        asm_low = SegmentAssessment(
            segment_id="seg_low_cov",
            model_version="saferoute-yolo11-v1",
            coverage=low_cov,
            aggregate_hazard=0.0,
            status=AssessmentStatus.PARTIALLY_ASSESSED,
        )

        res = self.engine.score_segment(asm_low, length_m=500.0)
        self.assertIsNotNone(res.segment_score)
        self.assertEqual(res.segment_score, 100.0)  # Computed formula
        self.assertTrue(res.is_suppressed)          # But suppressed due to low coverage
        self.assertTrue(any("Insufficient imagery coverage" in lim for lim in res.limitations))

    def test_route_scoring_length_weighted_aggregation(self):
        """Verify multi-segment length-weighted route aggregation: sum(L_i * S_i) / sum(L_i)."""
        cov = CoverageInfo(images_total=5, images_used=5, fraction=1.0)
        # Segment A: 200m, hazard 0.0 -> S = 100.0
        asm_a = SegmentAssessment(
            segment_id="seg_a",
            model_version="saferoute-yolo11-v1",
            coverage=cov,
            aggregate_hazard=0.0,
            status=AssessmentStatus.ASSESSED,
        )
        # Segment B: 800m, 8 hazard -> L=0.8km -> H=10.0 -> S = 100 * exp(-1.0) = 36.79
        asm_b = SegmentAssessment(
            segment_id="seg_b",
            model_version="saferoute-yolo11-v1",
            coverage=cov,
            aggregate_hazard=8.0,
            status=AssessmentStatus.ASSESSED,
        )

        route_res = self.engine.score_route(
            route_id="route_ab",
            segment_assessments=[asm_a, asm_b],
            segment_lengths_m=[200.0, 800.0],
        )

        # Expected score: (200 * 100.0 + 800 * 36.79) / 1000 = (20000 + 29432) / 1000 = 49.43
        score_a = self.engine.score_segment(asm_a, 200.0).segment_score
        score_b = self.engine.score_segment(asm_b, 800.0).segment_score
        expected_route = round((200.0 * score_a + 800.0 * score_b) / 1000.0, 2)

        self.assertEqual(route_res.route_score, expected_route)
        self.assertEqual(route_res.status, AssessmentStatus.ASSESSED)
        self.assertEqual(len(route_res.segment_scores), 2)

    def test_route_scoring_partial_coverage(self):
        """Partially assessed route correctly computes score over assessed segments and flags status."""
        cov_ok = CoverageInfo(images_total=5, images_used=5, fraction=1.0)
        cov_missing = CoverageInfo(images_total=0, images_used=0, fraction=0.0)

        asm_a = SegmentAssessment(
            segment_id="seg_a",
            model_version="saferoute-yolo11-v1",
            coverage=cov_ok,
            aggregate_hazard=0.0,
            status=AssessmentStatus.ASSESSED,
        )
        asm_b = SegmentAssessment(
            segment_id="seg_b",
            model_version="saferoute-yolo11-v1",
            coverage=cov_missing,
            aggregate_hazard=0.0,
            status=AssessmentStatus.UNASSESSED,
        )

        route_res = self.engine.score_route(
            route_id="route_partial",
            segment_assessments=[asm_a, asm_b],
            segment_lengths_m=[400.0, 600.0],
        )

        # Only seg_a is assessed (400m with score 100.0)
        self.assertEqual(route_res.route_score, 100.0)
        self.assertEqual(route_res.status, AssessmentStatus.PARTIALLY_ASSESSED)
        self.assertTrue(any("Partial route coverage" in lim for lim in route_res.limitations))

    def test_route_scoring_all_unassessed(self):
        """Route with zero coverage returns None score and unassessed status."""
        cov_missing = CoverageInfo(images_total=0, images_used=0, fraction=0.0)
        asm = SegmentAssessment(
            segment_id="seg_none",
            model_version="saferoute-yolo11-v1",
            coverage=cov_missing,
            aggregate_hazard=0.0,
            status=AssessmentStatus.UNASSESSED,
        )
        route_res = self.engine.score_route("route_zero", [asm], [500.0])
        self.assertIsNone(route_res.route_score)
        self.assertEqual(route_res.status, AssessmentStatus.UNASSESSED)

    def test_config_hash_emission(self):
        """Rule 17: Traceability hash must be a valid 64-character SHA-256 hex string."""
        hash_val = compute_config_hash(self.config_path)
        self.assertEqual(len(hash_val), 64)
        self.assertEqual(self.engine.config_hash, hash_val)

        cov = CoverageInfo(images_total=2, images_used=2, fraction=1.0)
        asm = SegmentAssessment(
            segment_id="seg_h",
            model_version="saferoute-yolo11-v1",
            coverage=cov,
            aggregate_hazard=1.0,
        )
        route_res = self.engine.score_route("route_hash", [asm])
        self.assertEqual(route_res.config_hash, hash_val)

    def test_schema_serialization_and_isolation(self):
        """Rule 11 & Rule 12: Ensure serialization matches ARCHITECTURE §7 and contains no facility data."""
        cov = CoverageInfo(images_total=5, images_used=5, fraction=1.0)
        asm = SegmentAssessment(
            segment_id="seg_iso",
            model_version="saferoute-yolo11-v1",
            coverage=cov,
            aggregate_hazard=2.5,
            status=AssessmentStatus.ASSESSED,
        )
        route_res = self.engine.score_route("route_iso", [asm], [300.0])
        d = route_res.to_dict()

        # Structural assertions
        self.assertIn("route_id", d)
        self.assertIn("route_score", d)
        self.assertIn("coverage", d)
        self.assertIn("config_hash", d)
        self.assertIn("status", d)
        self.assertIn("segment_scores", d)

        # Rule 11: Facility isolation
        self.assertNotIn("police_stations", d)
        self.assertNotIn("hospitals", d)
        self.assertNotIn("lighting_score", d)
        for s in d["segment_scores"]:
            self.assertNotIn("police", s)
            self.assertNotIn("hospitals", s)


if __name__ == "__main__":
    unittest.main()
