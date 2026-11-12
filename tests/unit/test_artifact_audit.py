"""Phase 42 / P1 artifact-audit tests.

The audit must be able to document a missing checkpoint/dataset honestly, and it
must be structurally unable to turn that state into measured detector metrics.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

from src.evaluation import artifact_audit
from src.evaluation.artifact_audit import (
    EXPECTED_V1_SHA256,
    EXPECTED_V2_PROVENANCE,
    EXPECTED_V2_SHA256,
    build_audit_bundle,
    candidate_overlap_probe,
    scan_for_checkpoints,
    write_audit_artifacts,
)
from src.evaluation.dataset_validation import compute_file_sha256


def _write_configs(root: Path, checkpoint: Path) -> tuple[Path, Path]:
    detection = root / "detection.yaml"
    detection.write_text(
        "metadata:\n"
        '  version: "detect-v2"\n'
        '  model_version: "saferoute-yolo11-v2"\n'
        "model:\n"
        f'  checkpoint: "{checkpoint.as_posix()}"\n'
        "inference:\n"
        "  imgsz: 640\n"
        "  conf: 0.25\n"
        "  iou: 0.45\n"
        "  max_det: 300\n"
        "supported_classes:\n"
        "  0: pothole\n"
        "  1: crack\n"
        "unsupported_classes:\n"
        "  - manhole\n",
        encoding="utf-8",
    )
    severity = root / "hazard_severity.yaml"
    severity.write_text(
        "metadata:\n"
        '  model_version: "saferoute-yolo11-v2"\n'
        "thresholds:\n"
        "  confidence_threshold: 0.25\n"
        "  dedup_iou_threshold: 0.45\n",
        encoding="utf-8",
    )
    return detection, severity


def _write_smoke_checkpoint(root: Path) -> Path:
    model_dir = root / "models" / "training" / "saferoute-yolo11-v2"
    weights = model_dir / "weights"
    weights.mkdir(parents=True, exist_ok=True)
    checkpoint = weights / "best.pt"
    checkpoint.write_bytes(b"not-a-real-checkpoint" * 64)
    (model_dir / "P0_SMOKE_SUBSTITUTE.json").write_text(
        json.dumps(
            {
                "status": "NON_PRODUCTION_P0_SMOKE_SUBSTITUTE",
                "installed_sha256": compute_file_sha256(checkpoint),
            }
        ),
        encoding="utf-8",
    )
    return checkpoint


def _pattern_image(index: int, size: int = 64) -> np.ndarray:
    x = np.linspace(0.0, 1.0, size, endpoint=False)
    y = np.linspace(0.0, 1.0, size, endpoint=False)
    fx = 1 + (index % 6)
    fy = 1 + ((index // 6) % 6)
    gray = 128.0 + 60.0 * np.sin(2 * np.pi * fx * x)[None, :] + 60.0 * np.cos(
        2 * np.pi * fy * y
    )[:, None]
    gray = np.clip(gray, 0, 255).astype(np.uint8)
    return np.stack([gray, np.roll(gray, 3, axis=1), gray[::-1, :]], axis=-1)


class TestArtifactAudit(unittest.TestCase):
    def test_historical_hashes_are_pinned(self) -> None:
        self.assertEqual(len(EXPECTED_V2_SHA256), 64)
        self.assertEqual(len(EXPECTED_V1_SHA256), 64)
        self.assertNotEqual(EXPECTED_V2_SHA256, EXPECTED_V1_SHA256)
        self.assertTrue(EXPECTED_V2_PROVENANCE)

    def test_smoke_checkpoint_is_refused_and_not_reported_as_v2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = _write_smoke_checkpoint(root)
            detection, severity = _write_configs(root, checkpoint)

            bundle = build_audit_bundle(
                root,
                detection_config=detection,
                severity_config=severity,
                check_candidate_overlap=False,
            )

            self.assertEqual(bundle.status.value, "NOT_ASSESSED")
            self.assertTrue(bundle.evaluation["artifacts"]["p0_smoke_substitute"])
            self.assertFalse(
                bundle.evaluation["artifacts"]["checkpoint_matches_expected_v2"]
            )
            self.assertIn(
                "p0_smoke_substitute_present_and_refused",
                bundle.evaluation["blockers"],
            )
            self.assertFalse(bundle.evaluation["evaluation_executed"])
            self.assertIsNone(bundle.evaluation["metrics"]["overall"])
            self.assertFalse(bundle.evaluation["stage_a"]["ran"])
            self.assertFalse(bundle.evaluation["stage_b"]["ran"])

    def test_missing_checkpoint_and_dataset_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = root / "models" / "training" / "v2" / "weights" / "best.pt"
            detection, severity = _write_configs(root, checkpoint)

            bundle = build_audit_bundle(
                root,
                detection_config=detection,
                severity_config=severity,
                check_candidate_overlap=False,
            )

            self.assertIn("genuine_checkpoint_missing", bundle.evaluation["blockers"])
            self.assertIn("independent_dataset_missing", bundle.evaluation["blockers"])
            self.assertFalse(bundle.evaluation["dataset"]["exists"])
            self.assertFalse(bundle.evaluation["dataset"]["layout_complete"])
            self.assertIsNone(bundle.evaluation["metrics"]["per_class"])
            self.assertEqual(bundle.evaluation["p1_status"], "NOT_ASSESSED")

    def test_missing_split_manifest_is_not_reported_as_date_atomic_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = _write_smoke_checkpoint(root)
            detection, severity = _write_configs(root, checkpoint)
            bundle = build_audit_bundle(
                root,
                detection_config=detection,
                severity_config=severity,
                check_candidate_overlap=False,
            )
            check = {
                item["check"]: item for item in bundle.leakage["checks"]
            }["same_source_split_date_atomicity"]
            self.assertEqual(check["status"], "NOT_ASSESSED")

    def test_checkpoint_search_hashes_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "archive" / "best.pt"
            candidate.parent.mkdir(parents=True)
            candidate.write_bytes(b"\0" * 1_100_000)

            result = scan_for_checkpoints([root])
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["candidates"][0]["sha256"], compute_file_sha256(candidate))
            self.assertEqual(result["expected_v2_matches"], [])

    def test_candidate_overlap_detects_exact_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "reference.jpg"
            candidate = root / "candidate.jpg"
            cv2.imwrite(str(reference), _pattern_image(1))
            shutil.copyfile(reference, candidate)

            probe = candidate_overlap_probe([candidate], [reference])
            self.assertEqual(probe["exact_match_count"], 1)
            self.assertEqual(probe["near_match_pair_count"], 1)

    def test_candidate_overlap_detects_near_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "reference.png"
            candidate = root / "candidate.png"
            image = _pattern_image(2)
            brighter = np.clip(image.astype(int) + 3, 0, 255).astype(np.uint8)
            cv2.imwrite(str(reference), image)
            cv2.imwrite(str(candidate), brighter)

            self.assertNotEqual(
                compute_file_sha256(reference), compute_file_sha256(candidate)
            )
            probe = candidate_overlap_probe([candidate], [reference])
            self.assertEqual(probe["exact_match_count"], 0)
            self.assertGreaterEqual(probe["near_match_pair_count"], 1)

    def test_candidate_overlap_reports_disjoint_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "reference.jpg"
            candidate = root / "candidate.jpg"
            cv2.imwrite(str(reference), _pattern_image(0))
            cv2.imwrite(str(candidate), _pattern_image(17))
            probe = candidate_overlap_probe([candidate], [reference])
            self.assertEqual(probe["exact_match_count"], 0)
            self.assertEqual(probe["near_match_pair_count"], 0)

    def test_write_audit_artifacts_writes_three_blocked_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = _write_smoke_checkpoint(root)
            detection, severity = _write_configs(root, checkpoint)
            output = root / "reports"

            summary = write_audit_artifacts(
                root,
                detection_config=detection,
                severity_config=severity,
                output_dir=output,
                check_candidate_overlap=False,
            )

            self.assertEqual(summary["status"], "NOT_ASSESSED")
            for name in (
                "phase42_independent_evaluation.json",
                "phase42_leakage_audit.json",
                "phase42_artifact_manifest.json",
            ):
                payload = json.loads((output / name).read_text(encoding="utf-8"))
                self.assertEqual(payload["status"], "NOT_ASSESSED")

            evaluation = json.loads(
                (output / "phase42_independent_evaluation.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(evaluation["evaluation_executed"])
            self.assertIsNone(evaluation["metrics"]["overall"])

    def test_audit_does_not_modify_configs_or_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = _write_smoke_checkpoint(root)
            detection, severity = _write_configs(root, checkpoint)
            before = {
                path: compute_file_sha256(path)
                for path in (checkpoint, detection, severity)
            }

            write_audit_artifacts(
                root,
                detection_config=detection,
                severity_config=severity,
                output_dir=root / "reports",
                check_candidate_overlap=False,
            )

            after = {
                path: compute_file_sha256(path)
                for path in (checkpoint, detection, severity)
            }
            self.assertEqual(before, after)

    def test_genuine_and_complete_inputs_refuse_blocked_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = _write_smoke_checkpoint(root)
            detection, severity = _write_configs(root, checkpoint)
            independent = root / "data" / "independent"
            (independent / "images" / "test").mkdir(parents=True)
            (independent / "labels" / "test").mkdir(parents=True)
            (independent / "manifests").mkdir(parents=True)
            (independent / "dataset.yaml").write_text("names: {0: pothole, 1: crack}\n")
            (independent / "manifests" / "independent_manifest.json").write_text("{}")

            with mock.patch.object(
                artifact_audit, "EXPECTED_V2_SHA256", compute_file_sha256(checkpoint)
            ):
                with self.assertRaises(RuntimeError):
                    build_audit_bundle(
                        root,
                        detection_config=detection,
                        severity_config=severity,
                        check_candidate_overlap=False,
                    )


if __name__ == "__main__":
    unittest.main()
