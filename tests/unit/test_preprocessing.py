"""Unit tests for SafeRoute AI OpenCV preprocessing pipeline.

Verifies:
1. Valid images -> status `ok`
2. Zero-byte files -> status `empty`
3. Truncated/corrupted bytes -> status `corrupt`
4. Non-existent files -> status `unreadable`
5. Unsupported extensions -> status `unsupported`
6. Small images below threshold -> status `too_small`
7. Determinism: identical input yields identical output
8. Non-destructiveness: original image array and file bytes remain unaltered
9. Visualisation: drawn on a copy, original unchanged
"""

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np

from src.preprocessing.pipeline import (
    ImageStatusCode,
    ImageStatus,
    PreparedImage,
    DetectionBox,
    PreprocessingPipeline,
    validate_image,
    preprocess,
    prepare_inference_input,
    visualise,
)


class TestPreprocessingPipeline(unittest.TestCase):
    """Test suite for preprocessing, validation, determinism, and safety."""

    def setUp(self):
        self.pipeline = PreprocessingPipeline()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Create a valid synthetic image (100x100 BGR)
        self.valid_img_array = np.zeros((100, 100, 3), dtype=np.uint8)
        # Add some color gradients to make it distinct
        self.valid_img_array[:, :, 0] = np.linspace(0, 255, 100, dtype=np.uint8)
        self.valid_img_array[:, :, 1] = 128
        self.valid_img_array[:, :, 2] = 200

        self.valid_img_file = self.temp_path / "valid_test.jpg"
        cv2.imwrite(str(self.valid_img_file), self.valid_img_array)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_validation_valid_image(self):
        """Valid image should decode successfully and return OK status."""
        status = self.pipeline.validate_image(self.valid_img_file)
        self.assertTrue(status.is_valid)
        self.assertEqual(status.code, ImageStatusCode.OK)
        self.assertEqual(status.width, 100)
        self.assertEqual(status.height, 100)
        self.assertEqual(status.channels, 3)

    def test_validation_empty_file(self):
        """Zero-byte file should be classified as EMPTY and invalid."""
        empty_file = self.temp_path / "empty.jpg"
        empty_file.touch()
        status = self.pipeline.validate_image(empty_file)
        self.assertFalse(status.is_valid)
        self.assertEqual(status.code, ImageStatusCode.EMPTY)

    def test_validation_unreadable_missing_file(self):
        """Non-existent file should be classified as UNREADABLE."""
        missing_file = self.temp_path / "does_not_exist.jpg"
        status = self.pipeline.validate_image(missing_file)
        self.assertFalse(status.is_valid)
        self.assertEqual(status.code, ImageStatusCode.UNREADABLE)

    def test_validation_corrupt_file(self):
        """Truncated/corrupt bytes should be classified as CORRUPT."""
        corrupt_file = self.temp_path / "corrupt.jpg"
        with open(corrupt_file, "wb") as f:
            f.write(b"\xFF\xD8\xFF\xE0" + b"random_corrupt_bytes_not_an_image")
        status = self.pipeline.validate_image(corrupt_file)
        self.assertFalse(status.is_valid)
        self.assertEqual(status.code, ImageStatusCode.CORRUPT)

    def test_validation_unsupported_extension(self):
        """Files with unsupported extensions should be classified as UNSUPPORTED."""
        text_file = self.temp_path / "image.txt"
        with open(text_file, "w") as f:
            f.write("not an image")
        status = self.pipeline.validate_image(text_file)
        self.assertFalse(status.is_valid)
        self.assertEqual(status.code, ImageStatusCode.UNSUPPORTED)

    def test_validation_too_small(self):
        """Images below min_width or min_height should be flagged as TOO_SMALL."""
        tiny_array = np.zeros((16, 16, 3), dtype=np.uint8)
        tiny_file = self.temp_path / "tiny.png"
        cv2.imwrite(str(tiny_file), tiny_array)
        status = self.pipeline.validate_image(tiny_file)
        self.assertFalse(status.is_valid)
        self.assertEqual(status.code, ImageStatusCode.TOO_SMALL)

    def test_determinism(self):
        """Identical input images must yield bit-identical preprocessed results."""
        prep1 = self.pipeline.preprocess(self.valid_img_array)
        prep2 = self.pipeline.preprocess(self.valid_img_array)
        
        np.testing.assert_array_equal(prep1.image, prep2.image)
        self.assertEqual(prep1.target_shape, prep2.target_shape)
        self.assertEqual(prep1.ratio, prep2.ratio)
        self.assertEqual(prep1.pad, prep2.pad)

    def test_original_image_array_preservation(self):
        """The preprocessing function must not mutate the input array."""
        copy_before = self.valid_img_array.copy()
        _ = self.pipeline.preprocess(self.valid_img_array)
        np.testing.assert_array_equal(self.valid_img_array, copy_before)

    def test_original_file_preservation(self):
        """Validating and reading an image file must not modify file contents on disk."""
        with open(self.valid_img_file, "rb") as f:
            hash_before = hashlib.sha256(f.read()).hexdigest()

        status = self.pipeline.validate_image(self.valid_img_file)
        self.assertTrue(status.is_valid)

        with open(self.valid_img_file, "rb") as f:
            hash_after = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(hash_before, hash_after)

    def test_inference_input_preparation(self):
        """Inference input should be float32 in range [0.0, 1.0] with shape (3, H, W)."""
        tensor, prepared = self.pipeline.prepare_inference_input(self.valid_img_array)
        self.assertEqual(tensor.dtype, np.float32)
        self.assertEqual(tensor.shape[0], 3)
        self.assertEqual(tensor.shape[1], prepared.target_shape[0])
        self.assertEqual(tensor.shape[2], prepared.target_shape[1])
        self.assertTrue(0.0 <= tensor.min() <= tensor.max() <= 1.0)

    def test_visualise_does_not_mutate_input(self):
        """Visualising bounding boxes must return a new canvas without mutating original array."""
        copy_before = self.valid_img_array.copy()
        detections = [
            DetectionBox(class_name="pothole", confidence=0.88, bbox=(10.0, 10.0, 40.0, 40.0)),
            DetectionBox(class_name="crack", confidence=0.75, bbox=(50.0, 50.0, 80.0, 80.0)),
        ]
        
        annotated_path = self.temp_path / "annotated.jpg"
        canvas = self.pipeline.visualise(self.valid_img_array, detections, output_path=annotated_path)

        # Original array must be unchanged
        np.testing.assert_array_equal(self.valid_img_array, copy_before)
        # Canvas must differ (it has drawn boxes)
        self.assertFalse(np.array_equal(canvas, self.valid_img_array))
        # Annotated file must exist and be valid
        self.assertTrue(annotated_path.exists())
        self.assertGreater(annotated_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
