"""PHASE 44 - production detection-validation recommendation gate.

These tests pin the safety behaviour that an unvalidated *production* detector
can never produce a safest-route recommendation, while injected test detectors
remain exempt (they are explicitly labelled unverified by the pipeline).

The gate only removes the recommendation/ranking claim; deterministic scores,
thresholds and the risk formula are untouched (Rule 7).
"""

import unittest

from src.api.pipeline import SafetyAnalysisPipeline


class TestDetectionValidationGate(unittest.TestCase):
    def _pipeline(self, production: bool, validated: bool) -> SafetyAnalysisPipeline:
        pipeline = SafetyAnalysisPipeline()
        pipeline._production_detector = production
        pipeline.detection_validated = validated
        pipeline.model_status = "SMOKE_SUBSTITUTE"
        pipeline.model_version = "p0-smoke-substitute"
        return pipeline

    @staticmethod
    def _record():
        return {
            "recommendation": "rt-a",
            "comparison": {
                "recommended_route_id": "rt-a",
                "recommendation_status": "recommended",
                "comparability": "comparable",
                "recommendation_reasons": ["cleaner evidence"],
            },
            "limitations": [],
        }

    def test_unvalidated_production_suppresses_recommendation(self):
        record = self._record()
        self._pipeline(production=True, validated=False)._apply_detection_validation_gate(record)

        self.assertIsNone(record["recommendation"])
        self.assertIsNone(record["comparison"]["recommended_route_id"])
        self.assertEqual(record["comparison"]["recommendation_status"], "cannot_determine")
        self.assertEqual(record["comparison"]["comparability"], "detection_not_validated")
        self.assertEqual(record["comparison"]["recommendation_reasons"], [])
        self.assertIn("detection_not_validated", record["comparison"]["cannot_determine_reason"])

        gate = record["detection_validation"]
        self.assertTrue(gate["required_for_recommendation"])
        self.assertFalse(gate["validated"])
        self.assertTrue(gate["recommendation_suppressed"])
        self.assertEqual(gate["model_status"], "SMOKE_SUBSTITUTE")
        self.assertEqual(gate["model_version"], "p0-smoke-substitute")
        self.assertTrue(any(
            "no real-world safety recommendation" in note
            for note in record["limitations"]
        ))

    def test_validated_production_preserves_recommendation(self):
        record = self._record()
        self._pipeline(production=True, validated=True)._apply_detection_validation_gate(record)

        self.assertEqual(record["recommendation"], "rt-a")
        self.assertEqual(record["comparison"]["recommended_route_id"], "rt-a")
        self.assertFalse(record["detection_validation"]["recommendation_suppressed"])

    def test_injected_test_detector_is_exempt_but_disclosed(self):
        record = self._record()
        self._pipeline(production=False, validated=False)._apply_detection_validation_gate(record)

        self.assertEqual(record["recommendation"], "rt-a")
        self.assertFalse(record["detection_validation"]["required_for_recommendation"])
        self.assertFalse(record["detection_validation"]["recommendation_suppressed"])


if __name__ == "__main__":
    unittest.main()
