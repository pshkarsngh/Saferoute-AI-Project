"""Phase 42 — dataset integrity and leakage tests.

Verifies explicit failures for missing annotations, invalid labels and empty
datasets, deterministic freezing hashes, unsupported-annotation rejection, and
session/duplicate leakage detection.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from src.evaluation.dataset_validation import (
    DatasetImage,
    DatasetValidationError,
    EmptyDatasetError,
    MissingAnnotationError,
    collect_dataset,
)
from src.evaluation.leakage import (
    analyze_leakage,
    check_session_boundaries,
    hamming_distance,
    perceptual_hash,
)


def _write_image(path: Path, fill: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((64, 64, 3), fill, dtype=np.uint8)
    image[:, :, 0] = np.arange(64, dtype=np.uint8)[None, :]
    self_ok = cv2.imwrite(str(path), image)
    assert self_ok, f"could not write {path}"


def _write_dataset(
    root: Path,
    labels: dict[str, str],
    *,
    manifest_images: list[dict] | None = None,
) -> tuple[Path, Path | None]:
    (root / "images" / "test").mkdir(parents=True, exist_ok=True)
    for stem, content in labels.items():
        _write_image(root / "images" / "test" / f"{stem}.jpg", fill=40 + len(stem) * 7)
        label_path = root / "labels" / "test" / f"{stem}.txt"
        label_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.write_text(content, encoding="utf-8")

    dataset_yaml = root / "dataset.yaml"
    dataset_yaml.write_text(
        "path: .\n"
        "test: images/test\n"
        "names:\n"
        "  0: pothole\n"
        "  1: crack\n",
        encoding="utf-8",
    )
    manifest_path = None
    if manifest_images is not None:
        manifest_path = root / "manifests" / "independent_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "dataset_version": "test-1",
                    "annotation_version": "ann-1",
                    "provenance": {"source": "unit-test"},
                    "annotation": {"version": "ann-1", "policy": "unit-test-policy"},
                    "quality_control": {
                        "annotator_a": True,
                        "annotator_b": True,
                        "adjudication": True,
                    },
                    "images": manifest_images,
                }
            ),
            encoding="utf-8",
        )
    return dataset_yaml, manifest_path


class TestDatasetValidation(unittest.TestCase):
    def test_empty_label_is_a_valid_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, _ = _write_dataset(
                root,
                {
                    "pos": "0 0.5 0.5 0.2 0.2\n",
                    "neg": "",
                },
            )
            inventory = collect_dataset(dataset_yaml, workspace_root=root, split="test")
            self.assertEqual(inventory.image_count, 2)
            self.assertEqual(len(inventory.ground_truth), 1)
            self.assertEqual(inventory.negative_image_ids, ("neg",))
            self.assertEqual(inventory.class_counts, {"pothole": 1, "crack": 0})

    def test_missing_label_file_raises_not_silent_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, _ = _write_dataset(root, {"img": "0 0.5 0.5 0.2 0.2\n"})
            (root / "labels" / "test" / "img.txt").unlink()
            with self.assertRaises(MissingAnnotationError):
                collect_dataset(dataset_yaml, workspace_root=root)

    def test_malformed_label_line_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, _ = _write_dataset(root, {"img": "0 0.5 0.5 0.2\n"})
            with self.assertRaises(DatasetValidationError):
                collect_dataset(dataset_yaml, workspace_root=root)

    def test_invalid_box_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # YOLO center-x 1.2 pushes the right edge outside the image (1.3).
            dataset_yaml, _ = _write_dataset(root, {"img": "0 1.2 0.5 0.2 0.2\n"})
            with self.assertRaises(DatasetValidationError):
                collect_dataset(dataset_yaml, workspace_root=root)

    def test_boundary_rounding_in_yolo_label_is_accepted_and_clamped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # center-x 0.998, width 0.012 -> right edge 1.004 (0.4% overshoot).
            dataset_yaml, _ = _write_dataset(root, {"img": "0 0.998 0.5 0.012 0.2\n"})
            inventory = collect_dataset(dataset_yaml, workspace_root=root)
            self.assertEqual(len(inventory.ground_truth), 1)
            self.assertAlmostEqual(inventory.ground_truth[0].bbox_norm[2], 1.0)

    def test_unsupported_annotation_class_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, _ = _write_dataset(root, {"img": "2 0.5 0.5 0.2 0.2\n"})
            with self.assertRaises(DatasetValidationError):
                collect_dataset(dataset_yaml, workspace_root=root)

    def test_corrupt_image_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, _ = _write_dataset(root, {"img": "0 0.5 0.5 0.2 0.2\n"})
            (root / "images" / "test" / "img.jpg").write_bytes(b"not-an-image")
            with self.assertRaises(DatasetValidationError):
                collect_dataset(dataset_yaml, workspace_root=root)

    def test_empty_split_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, _ = _write_dataset(root, {})
            with self.assertRaises(EmptyDatasetError):
                collect_dataset(dataset_yaml, workspace_root=root)

    def test_dataset_hash_is_deterministic_and_content_sensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, _ = _write_dataset(root, {"img": "0 0.5 0.5 0.2 0.2\n"})
            first = collect_dataset(dataset_yaml, workspace_root=root)
            second = collect_dataset(dataset_yaml, workspace_root=root)
            self.assertEqual(first.dataset_sha256, second.dataset_sha256)

            (root / "labels" / "test" / "img.txt").write_text(
                "0 0.5 0.5 0.2 0.3\n", encoding="utf-8"
            )
            third = collect_dataset(dataset_yaml, workspace_root=root)
            self.assertNotEqual(first.dataset_sha256, third.dataset_sha256)

    def test_manifest_session_metadata_is_attached(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, manifest = _write_dataset(
                root,
                {"img": "0 0.5 0.5 0.2 0.2\n"},
                manifest_images=[
                    {
                        "image_id": "img",
                        "file": "images/test/img.jpg",
                        "session_id": "session-1",
                        "condition": "night",
                    }
                ],
            )
            inventory = collect_dataset(
                dataset_yaml, manifest_path=manifest, workspace_root=root
            )
            self.assertEqual(inventory.images[0].session_id, "session-1")
            self.assertEqual(inventory.images[0].condition, "night")
            self.assertAlmostEqual(
                hamming_distance(
                    perceptual_hash(inventory.images[0].image_path),
                    perceptual_hash(inventory.images[0].image_path),
                ),
                0,
            )


class TestLeakage(unittest.TestCase):
    def test_session_crossing_split_is_detected(self):
        images = [
            DatasetImage("a", Path("a.jpg"), Path("a.txt"), "train", {"session_id": "s1"}),
            DatasetImage("b", Path("b.jpg"), Path("b.txt"), "test", {"session_id": "s1"}),
        ]
        issues = check_session_boundaries(SimpleNamespace(images=images))
        self.assertTrue(any(issue.kind == "session_crosses_split" for issue in issues))

    def test_reference_session_overlap_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, manifest = _write_dataset(
                root,
                {"img": "0 0.5 0.5 0.2 0.2\n"},
                manifest_images=[
                    {
                        "image_id": "img",
                        "file": "images/test/img.jpg",
                        "session_id": "seen-before",
                    }
                ],
            )
            inventory = collect_dataset(
                dataset_yaml, manifest_path=manifest, workspace_root=root
            )
            report = analyze_leakage(
                inventory,
                reference_session_ids={"seen-before"},
                check_near_duplicates=False,
            )
            self.assertFalse(report.is_clean)
            self.assertTrue(
                any(issue.kind == "reference_session_overlap" for issue in report.errors)
            )

    def test_exact_duplicate_across_sessions_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, manifest = _write_dataset(
                root,
                {
                    "a": "0 0.5 0.5 0.2 0.2\n",
                    "b": "0 0.5 0.5 0.2 0.2\n",
                },
                manifest_images=[
                    {"image_id": "a", "file": "images/test/a.jpg", "session_id": "s1"},
                    {"image_id": "b", "file": "images/test/b.jpg", "session_id": "s2"},
                ],
            )
            # Make the byte content identical while keeping distinct filenames.
            (root / "images" / "test" / "b.jpg").write_bytes(
                (root / "images" / "test" / "a.jpg").read_bytes()
            )
            inventory = collect_dataset(
                dataset_yaml, manifest_path=manifest, workspace_root=root
            )
            report = analyze_leakage(inventory, check_near_duplicates=True)
            self.assertFalse(report.is_clean)
            self.assertTrue(
                any("across_sessions" in issue.kind for issue in report.errors)
            )

    def test_reference_image_near_duplicate_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, manifest = _write_dataset(
                root,
                {"a": "0 0.5 0.5 0.2 0.2\n"},
                manifest_images=[
                    {"image_id": "a", "file": "images/test/a.jpg", "session_id": "s1"}
                ],
            )
            inventory = collect_dataset(
                dataset_yaml, manifest_path=manifest, workspace_root=root
            )
            report = analyze_leakage(
                inventory,
                reference_image_paths=[inventory.images[0].image_path],
                check_near_duplicates=True,
            )
            self.assertFalse(report.is_clean)
            self.assertTrue(
                any(
                    issue.kind in {"reference_exact_duplicate", "reference_near_duplicate"}
                    for issue in report.errors
                )
            )

    def test_missing_session_metadata_is_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml, _ = _write_dataset(root, {"a": ""})
            inventory = collect_dataset(dataset_yaml, workspace_root=root)
            report = analyze_leakage(inventory, check_near_duplicates=False)
            self.assertTrue(
                any(issue.kind == "missing_session_metadata" for issue in report.warnings)
            )


if __name__ == "__main__":
    unittest.main()
