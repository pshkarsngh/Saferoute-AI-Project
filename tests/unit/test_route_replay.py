"""Phase 42 — route replay tests.

The replay must reuse the production aggregator and deterministic engine
unchanged, and must surface ranking/eligibility changes caused by detection
error without altering the production scoring path.
"""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.evaluation.dataset_validation import collect_dataset
from src.evaluation.matching import PredictionBox
from src.evaluation.route_replay import (
    RESEARCH_ELIGIBILITY_RULE,
    RouteReplayError,
    replay_routes,
    spearman_rank_correlation,
)
from src.risk.engine import DeterministicRiskEngine

POTHOLE_BOX = (0.10, 0.10, 0.30, 0.30)
EXTRA_BOXES = [
    (0.02, 0.02, 0.12, 0.12),
    (0.20, 0.02, 0.30, 0.12),
    (0.40, 0.02, 0.50, 0.12),
    (0.60, 0.02, 0.70, 0.12),
    (0.02, 0.20, 0.12, 0.30),
    (0.20, 0.20, 0.30, 0.30),
]


def _image(index: int) -> np.ndarray:
    x = np.linspace(0, 1, 64, endpoint=False)
    gray = (
        128.0
        + 60.0 * np.sin(2 * np.pi * (1 + index) * x)[None, :]
        + 40.0 * np.cos(2 * np.pi * (2 + index) * x)[:, None]
    )
    gray = np.clip(gray, 0, 255).astype(np.uint8)
    return np.stack([gray, np.roll(gray, index + 1, axis=1), gray], axis=-1)


def _build_replay_dataset(root: Path) -> Path:
    dataset_root = root / "data" / "independent"
    images_dir = dataset_root / "images" / "test"
    labels_dir = dataset_root / "labels" / "test"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    # Route A: six real potholes, none detected.
    assert cv2.imwrite(str(images_dir / "route-a.jpg"), _image(1))
    (labels_dir / "route-a.txt").write_text(
        "".join(
            f"0 {(box[0] + box[2]) / 2} {(box[1] + box[3]) / 2} "
            f"{box[2] - box[0]} {box[3] - box[1]}\n"
            for box in EXTRA_BOXES
        ),
        encoding="utf-8",
    )

    # Route B: one real pothole, detected.
    assert cv2.imwrite(str(images_dir / "route-b.jpg"), _image(2))
    (labels_dir / "route-b.txt").write_text(
        "0 0.2 0.2 0.2 0.2\n", encoding="utf-8"
    )

    dataset_yaml = dataset_root / "dataset.yaml"
    dataset_yaml.write_text(
        "path: .\ntest: images/test\nnames:\n  0: pothole\n  1: crack\n",
        encoding="utf-8",
    )
    manifest = dataset_root / "manifests" / "independent_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "dataset_version": "replay-1",
                "annotation_version": "ann-1",
                "provenance": {"source": "synthetic-unit-test"},
                "annotation": {"version": "ann-1", "policy": "unit-test"},
                "images": [
                    {
                        "image_id": "route-a",
                        "file": "images/test/route-a.jpg",
                        "session_id": "session-a",
                        "condition": "daylight",
                        "route_id": "route-a",
                        "segment_id": "segment-a",
                        "segment_length_m": 500.0,
                    },
                    {
                        "image_id": "route-b",
                        "file": "images/test/route-b.jpg",
                        "session_id": "session-b",
                        "condition": "night",
                        "route_id": "route-b",
                        "segment_id": "segment-b",
                        "segment_length_m": 500.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return dataset_yaml


class TestRouteReplay(unittest.TestCase):
    def test_detection_error_reverses_ranking_and_eligibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml = _build_replay_dataset(root)
            inventory = collect_dataset(dataset_yaml, workspace_root=root)
            predictions = {
                "route-a": [],
                "route-b": [PredictionBox("route-b", "pothole", 0.90, (0.10, 0.10, 0.30, 0.30))],
            }

            engine = DeterministicRiskEngine()
            before_formula = engine.compute_safety_score_formula(1.0)
            report = replay_routes(
                inventory, predictions, engine=engine, eligibility_min_score=60.0
            )
            after_formula = engine.compute_safety_score_formula(1.0)

            # Production formula unchanged by replay.
            self.assertEqual(before_formula, after_formula)
            self.assertAlmostEqual(
                after_formula, 100.0 * math.exp(-0.10 * 1.0), places=2
            )

            self.assertIn(("route-a", "route-b"), report.ranking_reversals)
            self.assertEqual(
                report.routes["route-a"].predicted_score, 100.0
            )
            self.assertLess(report.routes["route-a"].ground_truth_score, 100.0)
            self.assertTrue(report.routes["route-a"].prediction_changed_eligibility)
            self.assertAlmostEqual(report.rank_correlation, -1.0)
            self.assertTrue(report.enough_evidence)
            self.assertIn("research_only", report.eligibility_rule)
            self.assertIn("src/risk/engine.py is unchanged", report.caveats[0])

    def test_missing_route_metadata_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_yaml = _build_replay_dataset(root)
            inventory = collect_dataset(dataset_yaml, workspace_root=root)

            class _BrokenInventory:
                def __init__(self, images):
                    self.images = images

                def ground_truth_by_image(self):
                    return {}

            broken_images = tuple(
                image
                if image.image_id != "route-a"
                else type(image)(
                    image_id=image.image_id,
                    image_path=image.image_path,
                    label_path=image.label_path,
                    split=image.split,
                    metadata={k: v for k, v in image.metadata.items() if k != "route_id"},
                )
                for image in inventory.images
            )
            with self.assertRaises(RouteReplayError):
                replay_routes(_BrokenInventory(broken_images), {})

    def test_spearman_known_values(self):
        left = {"a": 1.0, "b": 2.0, "c": 3.0}
        right = {"a": 3.0, "b": 2.0, "c": 1.0}
        self.assertAlmostEqual(spearman_rank_correlation(left, right), -1.0)
        self.assertAlmostEqual(spearman_rank_correlation(left, left), 1.0)
        self.assertIsNone(spearman_rank_correlation({"a": 1.0}, {"a": 2.0}))

    def test_research_eligibility_is_explicitly_not_production(self):
        self.assertIn("research_only", RESEARCH_ELIGIBILITY_RULE)
        self.assertIn("does not alter production", RESEARCH_ELIGIBILITY_RULE)


if __name__ == "__main__":
    unittest.main()
