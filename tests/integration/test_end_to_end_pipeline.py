"""SafeRoute AI — End-to-End Pipeline Integration Tests.

Validates the complete chain:
Raw Image -> OpenCV Preprocessing -> YOLO11 Detector -> Severity Policy -> Hazard Aggregator -> Deterministic Risk Engine.

Governing documents:
- TRD §7, §8, §9
- ARCHITECTURE §5, §6, §7
- master_rules.md Rules 7, 9, 10, 11, 12, 14, 17
"""

import unittest
from pathlib import Path
import cv2

from src.preprocessing.pipeline import PreprocessingPipeline, ImageStatusCode
from src.detection.detector import HazardDetector, DetectionStatus
from src.risk.severity import SeverityPolicy
from src.risk.aggregate import HazardAggregator
from src.risk.engine import DeterministicRiskEngine
from src.risk.schemas import AssessmentStatus

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


class TestEndToEndPipeline(unittest.TestCase):
    """End-to-end integration test validating the entire vision-to-risk scoring pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.preprocessing = PreprocessingPipeline()
        cls.detector = HazardDetector(device="cpu")  # CPU keeps test isolated and fast
        cls.policy = SeverityPolicy()
        cls.aggregator = HazardAggregator(policy=cls.policy)
        cls.risk_engine = DeterministicRiskEngine()

        # Find sample images from qualitative samples
        sample_dir = WORKSPACE_ROOT / "logs" / "evaluation" / "qualitative_samples"
        cls.sample_images = sorted(list(sample_dir.glob("*.jpg")))
        if not cls.sample_images:
            # Fallback to test split
            test_txt = WORKSPACE_ROOT / "data" / "splits" / "test.txt"
            with open(test_txt, "r") as f:
                cls.sample_images = [Path(line.strip()) for line in f if line.strip()][:5]

    def test_pipeline_real_image_inference_to_score(self):
        """End-to-end: Real road image -> Preprocessing -> Detection -> Aggregation -> Risk Scoring."""
        self.assertGreater(len(self.sample_images), 0, "No test images found")
        test_img_path = self.sample_images[0]

        # Step 1: Preprocessing & validation
        validation_res = self.preprocessing.validate_image(test_img_path)
        self.assertEqual(validation_res.code, ImageStatusCode.OK)
        self.assertTrue(validation_res.is_valid)

        img_bgr = cv2.imread(str(test_img_path))
        prepared = self.preprocessing.preprocess(img_bgr)
        self.assertEqual(prepared.image.shape, (640, 640, 3))

        # Step 2: YOLO11 Hazard Detection
        det_result = self.detector.detect(test_img_path, image_id="img_e2e_01")
        # HazardDetector() loads the promoted v2 checkpoint via
        # config/detection.yaml; model_version identifies the loaded checkpoint.
        self.assertEqual(det_result.model_version, "saferoute-yolo11-v2")
        self.assertIn(det_result.status, [DetectionStatus.SUCCESS, DetectionStatus.NO_DETECTIONS])

        # Step 3: Severity Policy & Aggregation
        segment_assessment = self.aggregator.assess_segment(
            segment_id="seg_alpha",
            image_results=[det_result],
            expected_image_count=1,
            route_id="route_primary",
        )
        self.assertEqual(segment_assessment.status, AssessmentStatus.ASSESSED)
        self.assertEqual(segment_assessment.coverage.fraction, 1.0)
        self.assertGreaterEqual(segment_assessment.aggregate_hazard, 0.0)

        # Step 4: Deterministic Risk Engine Scoring
        seg_score_result = self.risk_engine.score_segment(segment_assessment, length_m=500.0)
        self.assertIsNotNone(seg_score_result.segment_score)
        self.assertGreaterEqual(seg_score_result.segment_score, 0.0)
        self.assertLessEqual(seg_score_result.segment_score, 100.0)
        self.assertFalse(seg_score_result.is_suppressed)

        # Step 5: Route-level aggregation
        route_safety = self.risk_engine.score_route(
            route_id="route_primary",
            segment_assessments=[segment_assessment],
            segment_lengths_m=[500.0],
        )
        self.assertEqual(route_safety.route_score, seg_score_result.segment_score)
        self.assertEqual(route_safety.status, AssessmentStatus.ASSESSED)
        self.assertEqual(len(route_safety.config_hash), 64)

    def test_pipeline_multi_segment_route_with_unassessed_gap(self):
        """End-to-end multi-segment route: Seg 1 (real imagery), Seg 2 (missing imagery -> Rule 9)."""
        self.assertGreaterEqual(len(self.sample_images), 2)
        img1 = self.sample_images[0]
        img2 = self.sample_images[1]

        # Segment 1: Assessed with 2 real images
        det1 = self.detector.detect(img1, image_id="img_s1_1")
        det2 = self.detector.detect(img2, image_id="img_s1_2")
        seg1_assessment = self.aggregator.assess_segment(
            segment_id="seg_01",
            image_results=[det1, det2],
            expected_image_count=2,
            route_id="route_mixed",
        )

        # Segment 2: Unassessed (0 images available)
        seg2_assessment = self.aggregator.assess_segment(
            segment_id="seg_02",
            image_results=[],
            expected_image_count=2,
            route_id="route_mixed",
        )

        self.assertEqual(seg1_assessment.status, AssessmentStatus.ASSESSED)
        self.assertEqual(seg2_assessment.status, AssessmentStatus.UNASSESSED)

        # Score full route
        route_result = self.risk_engine.score_route(
            route_id="route_mixed",
            segment_assessments=[seg1_assessment, seg2_assessment],
            segment_lengths_m=[600.0, 400.0],
        )

        # Invariant checks
        self.assertEqual(route_result.status, AssessmentStatus.PARTIALLY_ASSESSED)
        self.assertEqual(route_result.coverage.images_total, 4)
        self.assertEqual(route_result.coverage.images_used, 2)
        self.assertEqual(route_result.coverage.fraction, 0.50)

        # Seg 2 must not yield a safe score (Rule 9)
        seg2_res = route_result.segment_scores[1]
        self.assertIsNone(seg2_res.segment_score)
        self.assertTrue(seg2_res.is_suppressed)
        self.assertEqual(seg2_res.status, AssessmentStatus.UNASSESSED)

        # Route score must equal Seg 1's score since only Seg 1 was assessed
        seg1_res = route_result.segment_scores[0]
        self.assertEqual(route_result.route_score, seg1_res.segment_score)

        # Route limitations disclose missing coverage
        self.assertTrue(any("Partial route coverage" in lim for lim in route_result.limitations))

    def test_pipeline_determinism_across_complete_stack(self):
        """Rule 7: Running the complete pipeline twice yields bit-identical dictionaries."""
        img = self.sample_images[0]
        det_a = self.detector.detect(img, image_id="img_det_a")
        det_b = self.detector.detect(img, image_id="img_det_a")

        asm_a = self.aggregator.assess_segment("seg_d", [det_a], 1, "route_d")
        asm_b = self.aggregator.assess_segment("seg_d", [det_b], 1, "route_d")

        route_a = self.risk_engine.score_route("route_d", [asm_a], [500.0])
        route_b = self.risk_engine.score_route("route_d", [asm_b], [500.0])

        self.assertEqual(route_a.to_dict(), route_b.to_dict())

    def test_pipeline_zero_facility_and_llm_isolation(self):
        """Rule 11 & Rule 12: Output data contract strictly isolates road hazard from facilities and LLM."""
        img = self.sample_images[0]
        det = self.detector.detect(img)
        asm = self.aggregator.assess_segment("seg_iso", [det], 1)
        route_res = self.risk_engine.score_route("route_iso", [asm], [300.0])

        d = route_res.to_dict()
        forbidden_facility_keys = ["police", "hospital", "lighting", "facility_score"]
        forbidden_llm_keys = ["llm_summary", "llm_score", "prompt", "explanation_text"]

        for k in forbidden_facility_keys:
            self.assertNotIn(k, d)
        for k in forbidden_llm_keys:
            self.assertNotIn(k, d)


if __name__ == "__main__":
    unittest.main()
