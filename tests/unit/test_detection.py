"""Unit tests for the SafeRoute AI Hazard Detection Module.

Phase ID: PHASE_10
Tests failure paths, structured output schema, preprocessing integration,
and non-destructive visualization using Python stdlib unittest.
Governing rules: master_rules.md Rules 1, 5, 6, 7, 9, 14.
"""

import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import cv2

from src.detection import (
    HazardDetector,
    DetectionRecord,
    DetectionStatus,
    ImageDetectionResult,
    MODEL_VERSION,
    SUPPORTED_CLASSES,
)

WORKSPACE_ROOT = Path("D:/New folder (3)").resolve()
VALID_TEST_IMAGE = WORKSPACE_ROOT / "data" / "pothole_crack_manhole" / "data" / "images" / "20250216_164521.jpg"
APPROVED_CHECKPOINT = WORKSPACE_ROOT / "models" / "training" / "saferoute-yolo11-v1" / "weights" / "best.pt"


class TestHazardDetector(unittest.TestCase):
    """Test suite for HazardDetector inference, contracts, and error handling."""

    @classmethod
    def setUpClass(cls):
        assert APPROVED_CHECKPOINT.exists(), f"Approved checkpoint missing at {APPROVED_CHECKPOINT}"
        cls.detector = HazardDetector(checkpoint_path=APPROVED_CHECKPOINT)

    def test_detector_initialization(self):
        """Verify detector loads approved model and preprocessing pipeline."""
        self.assertEqual(self.detector.model_version, "saferoute-yolo11-v1")
        self.assertEqual(self.detector.detector_version, "detect-v2")
        self.assertEqual(self.detector.pipeline.version, "preprocess-v1")
        self.assertEqual(self.detector.checkpoint_path, APPROVED_CHECKPOINT.resolve())

    def test_missing_checkpoint_raises_explicit_error(self):
        """Verify that a missing checkpoint fails explicitly without silent fallback."""
        non_existent_ckpt = WORKSPACE_ROOT / "models" / "training" / "non_existent.pt"
        with self.assertRaises(FileNotFoundError) as ctx:
            HazardDetector(checkpoint_path=non_existent_ckpt)
        self.assertIn("not found", str(ctx.exception))
        self.assertIn("Silent fallback", str(ctx.exception))

    def test_detect_valid_image(self):
        """Verify normal inference produces structured records with valid fields."""
        self.assertTrue(VALID_TEST_IMAGE.exists(), f"Test image missing: {VALID_TEST_IMAGE}")
        
        result = self.detector.detect(
            image_input=VALID_TEST_IMAGE,
            image_id="test_img_001",
            route_id="route_1",
            segment_id="seg_A",
            conf=0.20,
        )

        self.assertIsInstance(result, ImageDetectionResult)
        self.assertEqual(result.model_version, "saferoute-yolo11-v1")
        self.assertEqual(result.pipeline_version, "preprocess-v1")
        self.assertEqual(result.image_id, "test_img_001")
        self.assertEqual(result.route_id, "route_1")
        self.assertEqual(result.segment_id, "seg_A")
        self.assertIsNone(result.error)
        self.assertIn("preprocess", result.timing_ms)
        self.assertIn("inference", result.timing_ms)
        self.assertIn("postprocess", result.timing_ms)

        # Check JSON serialization
        d_dict = result.to_dict()
        json_str = json.dumps(d_dict)
        self.assertIsInstance(json_str, str)

        # If detections are present, verify their contract
        for det in result.detections:
            self.assertIsInstance(det, DetectionRecord)
            self.assertIn(det.hazard_class, ("pothole", "crack"))
            self.assertGreaterEqual(det.confidence, 0.0)
            self.assertLessEqual(det.confidence, 1.0)
            self.assertEqual(len(det.bbox_xyxy), 4)
            self.assertEqual(len(det.bbox_norm), 4)
            self.assertGreaterEqual(det.bbox_norm[0], 0.0)
            self.assertLessEqual(det.bbox_norm[2], 1.0)
            self.assertGreaterEqual(det.bbox_xyxy[2], det.bbox_xyxy[0])
            self.assertGreaterEqual(det.bbox_xyxy[3], det.bbox_xyxy[1])

    def test_detect_invalid_image_path(self):
        """Verify non-existent image path returns explicit INVALID_IMAGE status."""
        invalid_path = WORKSPACE_ROOT / "data" / "non_existent_image.jpg"
        result = self.detector.detect(invalid_path)

        self.assertEqual(result.status, DetectionStatus.INVALID_IMAGE)
        self.assertEqual(result.detections, [])
        self.assertIsNotNone(result.error)
        self.assertIn("validation failed", result.error)

    def test_detect_corrupt_empty_file(self):
        """Verify zero-byte empty image returns explicit INVALID_IMAGE status."""
        temp_dir = WORKSPACE_ROOT / "tests" / "unit" / "_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / "empty.jpg"
        temp_path.write_bytes(b"")

        try:
            result = self.detector.detect(temp_path)
            self.assertEqual(result.status, DetectionStatus.INVALID_IMAGE)
            self.assertEqual(result.detections, [])
            self.assertTrue("empty" in result.error.lower() or "zero bytes" in result.error.lower())
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_empty_detections_distinct_from_safe(self):
        """Verify clean synthetic image returns NO_DETECTIONS, not safe proof."""
        blank_image = np.full((360, 640, 3), 128, dtype=np.uint8)
        result = self.detector.detect(blank_image, conf=0.50)

        self.assertEqual(result.status, DetectionStatus.NO_DETECTIONS)
        self.assertEqual(len(result.detections), 0)
        self.assertIsNone(result.error)

        # Invariant: detector does NOT calculate safety or risk scores (Rule 7, Rule 12)
        d_dict = result.to_dict()
        self.assertNotIn("safety_score", d_dict)
        self.assertNotIn("risk_score", d_dict)

    def test_non_destructive_visualisation(self):
        """Verify visualisation draws onto a copy and never overwrites source."""
        self.assertTrue(VALID_TEST_IMAGE.exists())
        temp_dir = WORKSPACE_ROOT / "tests" / "unit" / "_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        out_vis = temp_dir / "vis_output.jpg"

        try:
            orig_mtime = VALID_TEST_IMAGE.stat().st_mtime
            result = self.detector.detect(VALID_TEST_IMAGE, conf=0.20)
            saved_path = self.detector.visualise(VALID_TEST_IMAGE, result, out_vis)

            self.assertTrue(saved_path.exists())
            self.assertGreater(saved_path.stat().st_size, 0)
            self.assertEqual(VALID_TEST_IMAGE.stat().st_mtime, orig_mtime)

            # Overwriting the original must raise an explicit ValueError
            with self.assertRaises(ValueError):
                self.detector.visualise(VALID_TEST_IMAGE, result, VALID_TEST_IMAGE)
        finally:
            if out_vis.exists():
                out_vis.unlink()
            if temp_dir.exists():
                try:
                    temp_dir.rmdir()
                except OSError:
                    pass


    def test_grayscale_and_batch_inputs(self):
        """Robustness: grayscale (single-channel) and batch inputs are handled."""
        gray = np.full((240, 320), 100, dtype=np.uint8)
        r = self.detector.detect(gray, conf=0.5)
        self.assertIsInstance(r, ImageDetectionResult)
        batch = self.detector.detect_batch([gray, VALID_TEST_IMAGE], conf=0.3)
        self.assertEqual(len(batch), 2)
        self.assertTrue(all(isinstance(x, ImageDetectionResult) for x in batch))

    def test_detection_config_loaded(self):
        """Detection config supplies imgsz/max_det/augment settings."""
        self.assertIsInstance(self.detector.imgsz, int)
        self.assertGreater(self.detector.imgsz, 0)
        self.assertIsInstance(self.detector.max_det, int)
        self.assertIsInstance(self.detector.augment, bool)


if __name__ == "__main__":
    unittest.main()
