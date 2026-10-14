"""PHASE_22 focused tests: detection outcome / misleading-100 fix (Rule 9)."""

import unittest

from src.detection.schemas import DetectionRecord, DetectionStatus, ImageDetectionResult
from src.risk.aggregate import HazardAggregator
from src.risk.engine import DeterministicRiskEngine
from src.risk.schemas import AssessmentStatus, CoverageInfo, SegmentAssessment


def _asm(segment_id, status, hazards=(), cov=(0, 0, 0.0)):
    return SegmentAssessment(
        segment_id=segment_id, model_version="saferoute-yolo11-v1",
        coverage=CoverageInfo(images_total=cov[0], images_used=cov[1], fraction=cov[2]),
        hazards=list(hazards), aggregate_hazard=float(sum(getattr(h, "severity", 0) for h in hazards)),
        status=status,
    )


def _hazard():
    agg = HazardAggregator()
    det = DetectionRecord(model_version="saferoute-yolo11-v1", hazard_class="pothole",
                          confidence=0.6, bbox_xyxy=[10, 10, 60, 60], bbox_norm=[0.0, 0.0, 0.3, 0.3])
    return agg.process_detection(det)


class TestDetectionOutcome(unittest.TestCase):
    def setUp(self):
        self.engine = DeterministicRiskEngine()

    def test_no_hazards_detected_is_not_safe(self):
        r = self.engine.score_route("r1", [_asm("s1", AssessmentStatus.ASSESSED, cov=(2, 2, 1.0))], [300.0])
        self.assertEqual(r.route_score, 100.0)
        self.assertEqual(r.detection_outcome, "no_hazards_detected")
        self.assertIn("NOT proof", r.safety_note)

    def test_hazards_detected(self):
        r = self.engine.score_route("r1", [_asm("s1", AssessmentStatus.ASSESSED, hazards=[_hazard()], cov=(2, 2, 1.0))], [300.0])
        self.assertEqual(r.detection_outcome, "hazards_detected")
        self.assertGreaterEqual(r.hazards_total, 1)

    def test_unassessed_is_not_scored(self):
        r = self.engine.score_route("r1", [_asm("s1", AssessmentStatus.UNASSESSED, cov=(0, 0, 0.0))], [300.0])
        self.assertIsNone(r.route_score)
        self.assertEqual(r.detection_outcome, "unassessed")
        self.assertIn("unassessed", r.safety_note.lower())

    def test_failed_detector(self):
        r = self.engine.score_route("r1", [_asm("s1", AssessmentStatus.FAILED, cov=(2, 0, 0.0))], [300.0])
        self.assertEqual(r.detection_outcome, "detector_failed")

    def test_partial_zero_hazards_is_insufficient_coverage(self):
        r = self.engine.score_route(
            "r1",
            [_asm("s1", AssessmentStatus.ASSESSED, cov=(2, 2, 1.0)),
             _asm("s2", AssessmentStatus.UNASSESSED, cov=(0, 0, 0.0))],
            [300.0, 300.0],
        )
        self.assertEqual(r.detection_outcome, "insufficient_coverage")
        self.assertIn("NOT", r.safety_note)

    def test_outcome_serialized(self):
        r = self.engine.score_route("r1", [_asm("s1", AssessmentStatus.ASSESSED, cov=(2, 2, 1.0))], [300.0])
        d = r.to_dict()
        self.assertIn("detection_outcome", d)
        self.assertIn("safety_note", d)
        self.assertIn("hazards_total", d)


if __name__ == "__main__":
    unittest.main()
