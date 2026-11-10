"""Phase 42 — metric correctness tests.

Covers TP/FP/FN, per-class AP (including class separation), operational FP/km,
miss rate, Wilson intervals, session-clustered bootstrap, and explicit
insufficient-sample handling.
"""

from __future__ import annotations

import unittest

from src.evaluation.confidence_intervals import (
    clustered_bootstrap_ci,
    insufficient_sample,
    wilson_interval,
)
from src.evaluation.matching import (
    GroundTruthBox,
    PredictionBox,
    ScoredPrediction,
    match_dataset,
)
from src.evaluation.metrics import (
    average_precision,
    compute_ap_metrics,
    compute_counts,
    deduplicate_frame_false_positives,
    false_positives_per_km,
    miss_rate,
    operational_summary,
    safe_divide,
)

CLASSES = ["pothole", "crack"]
BOX_A = (0.10, 0.10, 0.30, 0.30)
BOX_B = (0.50, 0.50, 0.70, 0.70)


def _match(predictions, ground_truth, image_ids=("img1",), iou=0.5):
    return match_dataset(predictions, ground_truth, image_ids, iou, CLASSES)


def _scored(conf, is_tp):
    return ScoredPrediction(
        image_id="img1",
        class_name="pothole",
        confidence=conf,
        is_true_positive=is_tp,
    )


class TestCountMetrics(unittest.TestCase):
    def test_safe_divide_returns_none_for_zero_denominator(self):
        self.assertIsNone(safe_divide(1, 0))
        self.assertEqual(safe_divide(1, 2), 0.5)

    def test_precision_recall_and_f1(self):
        metric = compute_counts(tp=3, fp=1, fn=2)
        self.assertAlmostEqual(metric.precision, 0.75)
        self.assertAlmostEqual(metric.recall, 0.6)
        self.assertAlmostEqual(metric.f1, 2 * 0.75 * 0.6 / 1.35)
        self.assertEqual(metric.ground_truth_count, 5)
        self.assertEqual(metric.predicted_count, 4)

    def test_zero_denominators_are_none_not_one(self):
        metric = compute_counts(tp=0, fp=0, fn=0)
        self.assertIsNone(metric.precision)
        self.assertIsNone(metric.recall)
        self.assertIsNone(metric.f1)


class TestAveragePrecision(unittest.TestCase):
    def test_perfect_ap_is_one(self):
        self.assertEqual(average_precision([_scored(0.9, True)], 1), 1.0)

    def test_no_ground_truth_is_none_not_zero(self):
        self.assertIsNone(average_precision([_scored(0.9, False)], 0))

    def test_no_predictions_is_zero_when_ground_truth_exists(self):
        self.assertEqual(average_precision([], 2), 0.0)

    def test_101_point_interpolation_known_case(self):
        predictions = [
            _scored(0.90, True),
            _scored(0.80, False),
            _scored(0.70, True),
        ]
        # Precision is 1.0 up to recall 0.5, then 2/3; 51 points at 1.0 and
        # 50 points at 2/3 over the 101-point recall sweep.
        expected = (51 * 1.0 + 50 * (2.0 / 3.0)) / 101.0
        self.assertAlmostEqual(average_precision(predictions, 2), expected, places=6)

    def test_confidence_order_matters(self):
        good_order = [_scored(0.9, True), _scored(0.8, False)]
        bad_order = [_scored(0.9, False), _scored(0.8, True)]
        self.assertGreater(
            average_precision(good_order, 1),
            average_precision(bad_order, 1),
        )


class TestPerClassAP(unittest.TestCase):
    def test_strong_class_does_not_hide_weak_class(self):
        ground_truth = {
            "img1": [GroundTruthBox("img1", "pothole", BOX_A)],
            "img2": [GroundTruthBox("img2", "crack", BOX_B)],
        }
        predictions = {
            "img1": [PredictionBox("img1", "pothole", 0.9, BOX_A)],
            "img2": [],
        }
        matches = {
            threshold: _match(predictions, ground_truth, ("img1", "img2"), threshold)
            for threshold in (0.50, 0.75)
        }
        ap = compute_ap_metrics(matches, CLASSES)
        self.assertAlmostEqual(ap.per_class["pothole"].ap50, 1.0)
        self.assertAlmostEqual(ap.per_class["crack"].ap50, 0.0)
        self.assertAlmostEqual(ap.map50, 0.5)
        self.assertEqual(ap.classes_evaluated, ("pothole", "crack"))

    def test_missing_class_is_insufficient_not_hidden(self):
        ground_truth = {"img1": [GroundTruthBox("img1", "pothole", BOX_A)]}
        predictions = {"img1": [PredictionBox("img1", "pothole", 0.9, BOX_A)]}
        matches = {0.5: _match(predictions, ground_truth, ("img1",))}
        ap = compute_ap_metrics(matches, CLASSES)
        self.assertIsNone(ap.per_class["crack"].ap50)
        self.assertEqual(ap.per_class["crack"].status, "insufficient_sample")
        self.assertIn("crack", ap.classes_insufficient)
        self.assertAlmostEqual(ap.map50, 1.0)  # macro over evaluable classes only


class TestOperationalMetrics(unittest.TestCase):
    def test_fp_per_km_requires_distance(self):
        self.assertIsNone(false_positives_per_km(15, None))
        self.assertIsNone(false_positives_per_km(15, 0.0))
        self.assertEqual(false_positives_per_km(15, 10.0), 1.5)

    def test_miss_rate(self):
        self.assertIsNone(miss_rate(3, 0))
        self.assertEqual(miss_rate(3, 10), 0.3)

    def test_operational_summary_counts_and_rates(self):
        ground_truth = {
            "img1": [GroundTruthBox("img1", "pothole", BOX_A)],
            "img2": [GroundTruthBox("img2", "crack", BOX_B)],
        }
        predictions = {
            "img1": [PredictionBox("img1", "pothole", 0.9, BOX_A)],
            "img2": [PredictionBox("img2", "pothole", 0.8, BOX_B)],
        }
        match = _match(predictions, ground_truth, ("img1", "img2"))
        summary = operational_summary(match, distance_km=2.0, class_names=CLASSES)
        self.assertEqual(summary["overall"]["true_positives"], 1)
        self.assertEqual(summary["overall"]["false_positives"], 1)
        self.assertEqual(summary["overall"]["false_negatives"], 1)
        self.assertAlmostEqual(summary["overall"]["precision"], 0.5)
        self.assertAlmostEqual(summary["overall"]["recall"], 0.5)
        self.assertAlmostEqual(summary["overall"]["false_positives_per_km"], 0.5)
        self.assertEqual(summary["per_class"]["crack"]["status"], "ok")
        self.assertEqual(summary["per_class"]["crack"]["miss_rate"], 1.0)

    def test_frame_false_positive_deduplication_is_session_scoped(self):
        from types import SimpleNamespace

        observations = [
            SimpleNamespace(session_id="s1", class_name="pothole", bbox_norm=BOX_A),
            SimpleNamespace(session_id="s1", class_name="pothole", bbox_norm=(0.11, 0.10, 0.31, 0.30)),
            SimpleNamespace(session_id="s2", class_name="pothole", bbox_norm=BOX_A),
            SimpleNamespace(session_id=None, class_name="pothole", bbox_norm=BOX_A),
            SimpleNamespace(session_id=None, class_name="pothole", bbox_norm=BOX_A),
        ]
        # s1 collapses to one cluster, s2 is one, unknown sessions stay separate.
        self.assertEqual(deduplicate_frame_false_positives(observations), 4)


class TestUncertainty(unittest.TestCase):
    def test_wilson_interval_known_values(self):
        low, high = wilson_interval(9, 10)
        self.assertAlmostEqual(low, 0.5958, places=3)
        self.assertAlmostEqual(high, 0.9821, places=3)

    def test_wilson_interval_undefined_without_samples(self):
        self.assertIsNone(wilson_interval(0, 0))

    def test_insufficient_sample_threshold(self):
        self.assertTrue(insufficient_sample(29, 30))
        self.assertFalse(insufficient_sample(30, 30))

    def test_clustered_bootstrap_is_deterministic(self):
        from types import SimpleNamespace

        observations = [
            SimpleNamespace(cluster_id=f"s{i % 3}", success=i % 2)
            for i in range(12)
        ]
        statistic = lambda items: sum(item.success for item in items) / len(items)
        first = clustered_bootstrap_ci(observations, statistic, seed=7, n_resamples=200)
        second = clustered_bootstrap_ci(observations, statistic, seed=7, n_resamples=200)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.n_clusters, 3)
        self.assertEqual(first.status, "ok")

    def test_single_cluster_cannot_produce_bootstrap_ci(self):
        from types import SimpleNamespace

        observations = [SimpleNamespace(cluster_id="s1", success=1) for _ in range(10)]
        result = clustered_bootstrap_ci(
            observations, lambda items: 1.0, seed=1, n_resamples=50
        )
        self.assertEqual(result.status, "insufficient_sample")
        self.assertIsNone(result.low)
        self.assertIsNone(result.high)


if __name__ == "__main__":
    unittest.main()
