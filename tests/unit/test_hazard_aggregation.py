"""Unit tests for the SafeRoute AI Hazard Aggregation & Severity Policy Module.

Phase ID: PHASE_11
Verifies:
1. Severity policy loading from config (base severities, modulation bounds).
2. Explainability of severity calculations.
3. Confidence threshold filtering (< 0.25 filtered, >= 0.25 kept).
4. Spatial IoU de-duplication and tie-breaking.
5. Status propagation (assessed, partially_assessed, unassessed, failed).
6. Rule 9: Missing imagery is never zero risk.
7. Rule 7 & 12: No safety scores computed, zero LLM involvement.
"""

import json
import unittest
from pathlib import Path

from src.detection.schemas import DetectionRecord, DetectionStatus, ImageDetectionResult
from src.risk import (
    AssessmentStatus,
    CoverageInfo,
    HazardRecord,
    SegmentAssessment,
    SeverityPolicy,
    HazardAggregator,
    compute_iou,
)

WORKSPACE_ROOT = Path("D:/New folder (3)").resolve()
CONFIG_PATH = WORKSPACE_ROOT / "config" / "hazard_severity.yaml"


class TestHazardAggregation(unittest.TestCase):
    """Test suite for severity assignment, IoU deduplication, and segment aggregation."""

    def setUp(self):
        assert CONFIG_PATH.exists(), f"Severity config missing at {CONFIG_PATH}"
        self.policy = SeverityPolicy(config_path=CONFIG_PATH)
        self.aggregator = HazardAggregator(self.policy)

    def test_policy_loading_and_base_severities(self):
        """Verify severity policy loads config-driven base severities."""
        self.assertEqual(self.policy.version, "severity-v1")
        self.assertEqual(self.policy.model_version, "saferoute-yolo11-v1")
        self.assertEqual(self.policy.confidence_threshold, 0.25)
        self.assertEqual(self.policy.dedup_iou_threshold, 0.45)

        # Base severities
        self.assertEqual(self.policy.get_base_severity("pothole"), 3.0)
        self.assertEqual(self.policy.get_base_severity("crack"), 1.5)
        self.assertEqual(self.policy.get_base_severity("unknown_hazard"), 1.0)

    def test_severity_calculation_and_bounding(self):
        """Verify severity formula applies bounded modulation within [1.0, 5.0]."""
        # Pothole with high confidence and large area
        sev_high = self.policy.calculate_severity(
            hazard_class="pothole",
            confidence=0.90,
            bbox_norm=[0.1, 0.1, 0.6, 0.6],  # Area = 0.25
        )
        self.assertGreater(sev_high, 3.0)
        self.assertLessEqual(sev_high, 5.0)

        # Crack with minimal confidence and small area
        sev_low = self.policy.calculate_severity(
            hazard_class="crack",
            confidence=0.25,
            bbox_norm=[0.1, 0.1, 0.12, 0.12],
        )
        self.assertGreaterEqual(sev_low, 1.0)
        self.assertLessEqual(sev_low, 2.0)

    def test_severity_explanation_traceability(self):
        """Verify every severity assignment is mathematically explainable (Rule 7)."""
        explanation = self.policy.explain_severity(
            hazard_class="pothole",
            confidence=0.80,
            bbox_norm=[0.2, 0.2, 0.5, 0.5],
        )
        self.assertIn("base_severity", explanation)
        self.assertIn("area_factor", explanation)
        self.assertIn("confidence_factor", explanation)
        self.assertIn("final_severity", explanation)
        self.assertEqual(explanation["base_severity"], 3.0)
        self.assertGreater(explanation["final_severity"], 3.0)

    def test_iou_calculation(self):
        """Verify bounding box IoU calculation."""
        box1 = [10.0, 10.0, 50.0, 50.0]
        box2 = [10.0, 10.0, 50.0, 50.0]  # Exact match
        self.assertAlmostEqual(compute_iou(box1, box2), 1.0)

        box3 = [100.0, 100.0, 150.0, 150.0]  # Disjoint
        self.assertAlmostEqual(compute_iou(box1, box3), 0.0)

        box4 = [30.0, 10.0, 70.0, 50.0]  # 50% overlap
        iou = compute_iou(box1, box4)
        self.assertGreater(iou, 0.0)
        self.assertLess(iou, 1.0)

    def test_confidence_threshold_filtering(self):
        """Verify detections below confidence threshold are discarded."""
        det_low = DetectionRecord(
            model_version="saferoute-yolo11-v1",
            image_id="img_1",
            hazard_class="pothole",
            confidence=0.20,  # Below threshold 0.25
        )
        det_high = DetectionRecord(
            model_version="saferoute-yolo11-v1",
            image_id="img_1",
            hazard_class="pothole",
            confidence=0.35,  # Above threshold
        )

        h_low = self.aggregator.process_detection(det_low)
        self.assertIsNone(h_low)

        h_high = self.aggregator.process_detection(det_high)
        self.assertIsNotNone(h_high)
        self.assertEqual(h_high.hazard_class, "pothole")
        self.assertGreaterEqual(h_high.severity, 1.0)

    def test_iou_deduplication_tie_break(self):
        """Verify overlapping duplicate detections are suppressed, keeping higher conf."""
        # Two overlapping potholes
        d1 = DetectionRecord(
            model_version="saferoute-yolo11-v1",
            image_id="img_1",
            hazard_class="pothole",
            confidence=0.60,
            bbox_xyxy=[100.0, 100.0, 200.0, 200.0],
            bbox_norm=[0.15, 0.27, 0.31, 0.55],
        )
        d2 = DetectionRecord(
            model_version="saferoute-yolo11-v1",
            image_id="img_1",
            hazard_class="pothole",
            confidence=0.85,  # Higher confidence
            bbox_xyxy=[105.0, 102.0, 202.0, 201.0],  # ~90% IoU
            bbox_norm=[0.16, 0.28, 0.31, 0.55],
        )
        # Disjoint crack
        d3 = DetectionRecord(
            model_version="saferoute-yolo11-v1",
            image_id="img_1",
            hazard_class="crack",
            confidence=0.50,
            bbox_xyxy=[300.0, 300.0, 400.0, 350.0],
            bbox_norm=[0.46, 0.83, 0.62, 0.97],
        )

        deduped = self.aggregator.deduplicate_detections([d1, d2, d3])
        self.assertEqual(len(deduped), 2)
        # Pothole retained must be d2 with confidence 0.85
        retained_pothole = [d for d in deduped if d.hazard_class == "pothole"][0]
        self.assertEqual(retained_pothole.confidence, 0.85)

    def test_hazard_record_contract_schema(self):
        """Verify HazardRecord to_dict() matches TRD §8.1 specification."""
        det = DetectionRecord(
            model_version="saferoute-yolo11-v1",
            image_id="img-001",
            route_id="route-1",
            segment_id="seg-1-0",
            hazard_class="pothole",
            confidence=0.75,
            bbox_xyxy=[50.0, 60.0, 150.0, 180.0],
            bbox_norm=[0.07, 0.16, 0.23, 0.50],
        )
        h_rec = self.aggregator.process_detection(det)
        self.assertIsNotNone(h_rec)
        d_dict = h_rec.to_dict()

        # Check required fields from TRD §8.1
        expected_keys = {
            "model_version", "image_id", "route_id", "segment_id",
            "hazard_class", "confidence", "bbox_xyxy", "bbox_norm",
            "severity", "status", "error"
        }
        self.assertEqual(set(d_dict.keys()), expected_keys)
        self.assertEqual(d_dict["status"], "assessed")
        self.assertIsNone(d_dict["error"])
        # Ensure clean JSON serializability
        self.assertIsInstance(json.dumps(d_dict), str)

    def test_status_propagation_full_assessed(self):
        """Verify 100% image coverage produces ASSESSED status."""
        img_res = ImageDetectionResult(
            model_version="saferoute-yolo11-v1",
            pipeline_version="preprocess-v1",
            status=DetectionStatus.SUCCESS,
            image_id="frame_1",
            detections=[
                DetectionRecord(
                    model_version="saferoute-yolo11-v1",
                    image_id="frame_1",
                    hazard_class="pothole",
                    confidence=0.60,
                    bbox_xyxy=[10.0, 10.0, 50.0, 50.0],
                    bbox_norm=[0.01, 0.02, 0.07, 0.13],
                )
            ]
        )
        assessment = self.aggregator.assess_segment(
            segment_id="seg_01",
            image_results=[img_res],
            expected_image_count=1,
            route_id="route_A",
        )
        self.assertEqual(assessment.status, AssessmentStatus.ASSESSED)
        self.assertEqual(assessment.coverage.fraction, 1.0)
        self.assertEqual(len(assessment.hazards), 1)
        self.assertGreater(assessment.aggregate_hazard, 0.0)

    def test_status_propagation_missing_imagery_rule9(self):
        """Verify Rule 9: Missing imagery produces UNASSESSED status, NOT zero risk."""
        assessment = self.aggregator.assess_segment(
            segment_id="seg_missing",
            image_results=[],
            expected_image_count=0,
            route_id="route_A",
        )
        self.assertEqual(assessment.status, AssessmentStatus.UNASSESSED)
        self.assertEqual(assessment.coverage.fraction, 0.0)
        self.assertEqual(len(assessment.hazards), 0)
        # Check limitations explicitly warn that missing imagery != safe
        self.assertTrue(any("unassessed" in lim.lower() for lim in assessment.limitations))

    def test_status_propagation_partial_coverage(self):
        """Verify partial imagery produces PARTIALLY_ASSESSED status."""
        img_res = ImageDetectionResult(
            model_version="saferoute-yolo11-v1",
            pipeline_version="preprocess-v1",
            status=DetectionStatus.NO_DETECTIONS,
            image_id="frame_1",
            detections=[]
        )
        # Expected 2 images, but only 1 provided
        assessment = self.aggregator.assess_segment(
            segment_id="seg_partial",
            image_results=[img_res],
            expected_image_count=2,
            route_id="route_A",
        )
        self.assertEqual(assessment.status, AssessmentStatus.PARTIALLY_ASSESSED)
        self.assertEqual(assessment.coverage.fraction, 0.5)

    def test_status_propagation_failed_imagery(self):
        """Verify all failed images produce FAILED status."""
        failed_res = ImageDetectionResult(
            model_version="saferoute-yolo11-v1",
            pipeline_version="preprocess-v1",
            status=DetectionStatus.INVALID_IMAGE,
            image_id="corrupt_frame",
            error="Decode failure"
        )
        assessment = self.aggregator.assess_segment(
            segment_id="seg_fail",
            image_results=[failed_res],
            expected_image_count=1,
            route_id="route_A",
        )
        self.assertEqual(assessment.status, AssessmentStatus.FAILED)
        self.assertEqual(assessment.coverage.fraction, 0.0)

    def test_rule7_and_12_no_safety_scores_computed(self):
        """Verify that HazardAggregator computes NO route safety scores."""
        assessment = self.aggregator.assess_segment(
            segment_id="seg_01",
            image_results=[],
            expected_image_count=1,
        )
        d_dict = assessment.to_dict()
        # Segment score and route score belong to Phase 12 risk engine
        self.assertNotIn("segment_score", d_dict)
        self.assertNotIn("route_score", d_dict)
        self.assertNotIn("safety_score", d_dict)


if __name__ == "__main__":
    unittest.main()
