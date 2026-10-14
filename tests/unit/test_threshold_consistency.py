"""Focused test (PHASE_21): detector/aggregator confidence-threshold contract.

The aggregator drops any detection below `hazard_severity.yaml: confidence_threshold`.
If the detector runs at a LOWER threshold, detections in the gap are produced and
then silently discarded, which can yield "zero hazards -> score 100". This test
asserts the two thresholds agree. If it FAILS, the defect is real and must be
fixed in configuration (not by editing this test).
"""

import unittest
from pathlib import Path

import yaml

WS = Path(__file__).resolve().parent.parent.parent


from src.config.env import WORKSPACE_ROOT
from src.config.thresholds import assert_threshold_consistency, load_threshold_policy


class TestConfidenceThresholdConsistency(unittest.TestCase):
    def test_detector_and_aggregator_thresholds_match(self):
        det = yaml.safe_load((WS / "config" / "detection.yaml").read_text(encoding="utf-8"))
        sev = yaml.safe_load((WS / "config" / "hazard_severity.yaml").read_text(encoding="utf-8"))
        det_conf = float(det["inference"]["conf"])
        agg_conf = float(sev["thresholds"]["confidence_threshold"])
        self.assertEqual(
            det_conf, agg_conf,
            f"Detector conf ({det_conf}) != aggregator confidence_threshold ({agg_conf}); "
            f"detections in [{det_conf},{agg_conf}) are silently dropped.",
        )

    def test_policy_loader_reports_consistent(self):
        policy = load_threshold_policy()
        self.assertTrue(policy.consistent)

    def test_runtime_guard_accepts_consistent_configs(self):
        policy = assert_threshold_consistency()
        self.assertTrue(policy.consistent)

    def test_runtime_guard_rejects_inconsistent_configs(self):
        import tempfile
        d = Path(tempfile.mkdtemp(prefix="sr_thr_"))
        (d / "detection.yaml").write_text("inference:\n  conf: 0.10\n", encoding="utf-8")
        (d / "hazard_severity.yaml").write_text(
            "thresholds:\n  confidence_threshold: 0.30\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            assert_threshold_consistency(d / "detection.yaml", d / "hazard_severity.yaml")


if __name__ == "__main__":
    unittest.main()
