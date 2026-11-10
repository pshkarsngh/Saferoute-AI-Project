"""Phase 42 — detection matching tests.

Verifies class-aware one-to-one IoU matching, confidence ordering, invalid box
rejection, and the rule that missing annotations are never silent negatives.
"""

from __future__ import annotations

import unittest

from src.evaluation.matching import (
    BoxValidationError,
    GroundTruthBox,
    MatchingError,
    PredictionBox,
    compute_iou,
    match_dataset,
    match_image,
    validate_bbox_norm,
)

BOX = (0.10, 0.10, 0.30, 0.30)


class TestIoU(unittest.TestCase):
    def test_identical_boxes_have_iou_one(self):
        self.assertAlmostEqual(compute_iou(BOX, BOX), 1.0)

    def test_disjoint_boxes_have_iou_zero(self):
        self.assertEqual(compute_iou(BOX, (0.60, 0.60, 0.80, 0.80)), 0.0)

    def test_half_overlap(self):
        # Same 0.2x0.2 area, shifted so intersection is 0.1x0.2.
        self.assertAlmostEqual(
            compute_iou((0.0, 0.0, 0.2, 0.2), (0.1, 0.0, 0.3, 0.2)),
            0.1 * 0.2 / (0.04 + 0.04 - 0.02),
        )


class TestBoxValidation(unittest.TestCase):
    def test_valid_box_is_frozen_tuple(self):
        self.assertEqual(validate_bbox_norm([0.1, 0.2, 0.3, 0.4]), (0.1, 0.2, 0.3, 0.4))

    def test_wrong_length_rejected(self):
        with self.assertRaises(BoxValidationError):
            validate_bbox_norm([0.1, 0.2, 0.3])

    def test_nan_rejected(self):
        with self.assertRaises(BoxValidationError):
            validate_bbox_norm([0.1, float("nan"), 0.3, 0.4])

    def test_out_of_range_rejected(self):
        with self.assertRaises(BoxValidationError):
            validate_bbox_norm([-0.1, 0.0, 0.3, 0.4])
        with self.assertRaises(BoxValidationError):
            validate_bbox_norm([0.1, 0.2, 1.3, 0.4])

    def test_inverted_or_zero_area_rejected(self):
        with self.assertRaises(BoxValidationError):
            validate_bbox_norm([0.3, 0.2, 0.1, 0.4])
        with self.assertRaises(BoxValidationError):
            validate_bbox_norm([0.1, 0.2, 0.1, 0.4])

    def test_boundary_rounding_is_clamped_only_for_labels(self):
        # A center/size encoding can round a boundary box slightly outside [0, 1].
        self.assertEqual(
            validate_bbox_norm(
                (-0.001, 0.2, 1.004, 0.8), boundary_tolerance=0.01
            ),
            (0.0, 0.2, 1.0, 0.8),
        )
        # Production predictions keep the strict default.
        with self.assertRaises(BoxValidationError):
            validate_bbox_norm((-0.001, 0.2, 1.004, 0.8))

    def test_overshoot_beyond_label_tolerance_is_rejected(self):
        with self.assertRaises(BoxValidationError):
            validate_bbox_norm(
                (-0.02, 0.2, 1.05, 0.8), boundary_tolerance=0.01
            )


class TestImageMatching(unittest.TestCase):
    def test_same_box_different_class_is_not_a_true_positive(self):
        gt = [GroundTruthBox("img1", "pothole", BOX)]
        pred = [PredictionBox("img1", "crack", 0.9, BOX)]
        result = match_image(pred, gt)
        self.assertEqual(len(result.false_negatives), 1)
        self.assertFalse(result.scored_predictions[0].is_true_positive)

    def test_one_prediction_matches_only_one_ground_truth(self):
        gt = [
            GroundTruthBox("img1", "pothole", BOX),
            GroundTruthBox("img1", "pothole", (0.12, 0.12, 0.32, 0.32)),
        ]
        pred = [PredictionBox("img1", "pothole", 0.9, BOX)]
        result = match_image(pred, gt)
        self.assertEqual(sum(p.is_true_positive for p in result.scored_predictions), 1)
        self.assertEqual(len(result.false_negatives), 1)

    def test_highest_iou_ground_truth_wins(self):
        far = GroundTruthBox("img1", "pothole", (0.10, 0.10, 0.35, 0.35))
        near = GroundTruthBox("img1", "pothole", (0.11, 0.11, 0.30, 0.30))
        pred = [PredictionBox("img1", "pothole", 0.9, BOX)]
        result = match_image(pred, [far, near])
        self.assertIs(result.scored_predictions[0].matched_gt, near)

    def test_below_threshold_creates_fp_and_fn(self):
        gt = [GroundTruthBox("img1", "pothole", BOX)]
        pred = [PredictionBox("img1", "pothole", 0.9, (0.50, 0.50, 0.70, 0.70))]
        result = match_image(pred, gt, iou_threshold=0.5)
        self.assertFalse(result.scored_predictions[0].is_true_positive)
        self.assertEqual(len(result.false_negatives), 1)

    def test_confidence_order_controls_assignment(self):
        gt = [GroundTruthBox("img1", "pothole", BOX)]
        high = PredictionBox("img1", "pothole", 0.95, BOX)
        low = PredictionBox("img1", "pothole", 0.30, BOX)
        result = match_image([low, high], gt)
        # The higher-confidence prediction is considered first and wins.
        self.assertTrue(result.scored_predictions[0].is_true_positive)
        self.assertAlmostEqual(result.scored_predictions[0].confidence, 0.95)

    def test_unsupported_class_prediction_is_rejected_before_matching(self):
        gt = [GroundTruthBox("img1", "pothole", BOX)]
        pred = [PredictionBox("img1", "unsupported_class_2", 0.9, BOX, status="unsupported_class")]
        with self.assertRaises(MatchingError):
            match_image(pred, gt)

    def test_scored_prediction_retains_box_for_operational_dedup(self):
        gt = [GroundTruthBox("img1", "pothole", BOX)]
        pred = [PredictionBox("img1", "pothole", 0.9, BOX)]
        result = match_image(pred, gt)
        self.assertEqual(result.scored_predictions[0].bbox_norm, BOX)


class TestDatasetMatching(unittest.TestCase):
    def test_missing_annotation_entry_raises(self):
        predictions = {"img1": [PredictionBox("img1", "pothole", 0.9, BOX)]}
        ground_truth = {}
        with self.assertRaises(MatchingError):
            match_dataset(predictions, ground_truth, ["img1"])

    def test_prediction_for_unlisted_image_raises(self):
        ground_truth = {"img1": []}
        predictions = {"img2": [PredictionBox("img2", "pothole", 0.9, BOX)]}
        with self.assertRaises(MatchingError):
            match_dataset(predictions, ground_truth, ["img1"])

    def test_empty_image_set_raises(self):
        with self.assertRaises(MatchingError):
            match_dataset({}, {}, [])

    def test_per_class_counts(self):
        ground_truth = {
            "img1": [
                GroundTruthBox("img1", "pothole", BOX),
                GroundTruthBox("img1", "crack", (0.5, 0.5, 0.7, 0.7)),
            ],
            "img2": [],
        }
        predictions = {
            "img1": [PredictionBox("img1", "pothole", 0.9, BOX)],
            "img2": [],
        }
        match = match_dataset(predictions, ground_truth, ["img1", "img2"], class_names=["pothole", "crack"])
        self.assertEqual(match.per_class["pothole"].true_positives, 1)
        self.assertEqual(match.per_class["pothole"].ground_truth_count, 1)
        self.assertEqual(match.per_class["crack"].false_negatives, 1)
        self.assertEqual(match.false_positives, 0)
        self.assertEqual(match.false_negative_count, 1)


if __name__ == "__main__":
    unittest.main()
