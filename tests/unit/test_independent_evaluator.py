"""Phase 42 — independent evaluator orchestration tests.

Negative tests are the priority: missing weights, smoke substitution, config
drift, empty datasets, missing annotations, unsupported classes, invalid boxes,
confidence-contract violations, and missing-class evidence.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.detection.schemas import DetectionRecord, DetectionStatus, ImageDetectionResult
from src.evaluation.dataset_validation import (
    DatasetValidationError,
    EmptyDatasetError,
    MissingAnnotationError,
    compute_file_sha256,
)
from src.evaluation.evaluator import (
    EvaluationStatus,
    IndependentEvaluator,
    ModelIntegrityError,
    ProductionParityError,
    SmokeSubstituteError,
)

POTHOLE_BOX = (0.10, 0.10, 0.30, 0.30)
CRACK_BOX = (0.50, 0.50, 0.75, 0.60)


def _pattern_image(index: int) -> np.ndarray:
    x = np.linspace(0.0, 1.0, 64, endpoint=False)
    y = np.linspace(0.0, 1.0, 64, endpoint=False)
    fx = 1 + (index % 8)
    fy = 1 + ((index // 8) % 8)
    gray = 128.0 + 55.0 * np.sin(2 * np.pi * fx * x)[None, :] + 55.0 * np.cos(
        2 * np.pi * fy * y
    )[:, None]
    gray = np.clip(gray, 0, 255).astype(np.uint8)
    return np.stack([gray, np.roll(gray, index % 8, axis=1), gray[::-1, :]], axis=-1)


def _write_configs(
    root: Path,
    checkpoint: Path,
    *,
    conf: float = 0.25,
    severity_conf: float = 0.25,
    imgsz: int = 640,
) -> tuple[Path, Path]:
    detection = root / "detection.yaml"
    detection.write_text(
        "metadata:\n"
        '  version: "detect-v2"\n'
        '  model_version: "saferoute-yolo11-v2"\n'
        "model:\n"
        f'  checkpoint: "{checkpoint.as_posix()}"\n'
        "inference:\n"
        f"  imgsz: {imgsz}\n"
        f"  conf: {conf}\n"
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
        f"  confidence_threshold: {severity_conf}\n",
        encoding="utf-8",
    )
    return detection, severity


def _build_checkpoint(root: Path) -> Path:
    checkpoint = root / "models" / "saferoute-yolo11-v2" / "weights" / "best.pt"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_bytes(b"fake-serving-checkpoint-bytes")
    return checkpoint


def _build_dataset(
    root: Path,
    *,
    potholes: int = 30,
    cracks: int = 30,
    with_manifest: bool = True,
) -> dict[str, Any]:
    dataset_root = root / "data" / "independent"
    images_dir = dataset_root / "images" / "test"
    labels_dir = dataset_root / "labels" / "test"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    image_ids: list[str] = []
    gt_by_image: dict[str, list[tuple[str, tuple[float, float, float, float]]]] = {}
    metadata_images: list[dict[str, Any]] = []
    index = 0

    for class_name, count, box in (
        ("pothole", potholes, POTHOLE_BOX),
        ("crack", cracks, CRACK_BOX),
    ):
        for offset in range(count):
            image_id = f"{class_name}_{offset:03d}"
            image_path = images_dir / f"{image_id}.jpg"
            assert cv2.imwrite(str(image_path), _pattern_image(index))
            (labels_dir / f"{image_id}.txt").write_text(
                f"{0 if class_name == 'pothole' else 1} "
                f"{(box[0] + box[2]) / 2} {(box[1] + box[3]) / 2} "
                f"{box[2] - box[0]} {box[3] - box[1]}\n",
                encoding="utf-8",
            )
            image_ids.append(image_id)
            gt_by_image[image_id] = [(class_name, box)]
            metadata_images.append(
                {
                    "image_id": image_id,
                    "file": f"images/test/{image_id}.jpg",
                    "session_id": f"independent-session-{index % 6}",
                    "camera_id": f"camera-{index % 3}",
                    "condition": ["daylight", "night", "rain"][index % 3],
                    "route_id": f"route-{index % 4}",
                    "segment_id": f"segment-{index % 2}",
                    "segment_length_m": 500.0,
                    "distance_km": 0.02,
                    "split": "test",
                }
            )
            index += 1

    dataset_yaml = dataset_root / "dataset.yaml"
    dataset_yaml.write_text(
        "path: .\n"
        "test: images/test\n"
        "names:\n"
        "  0: pothole\n"
        "  1: crack\n",
        encoding="utf-8",
    )

    manifest_path = None
    if with_manifest:
        manifest_path = dataset_root / "manifests" / "independent_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "dataset_version": "independent-1.0",
                    "annotation_version": "annotation-1.0",
                    "provenance": {
                        "source": "independent field collection",
                        "collection": "outside-training-corpus",
                    },
                    "annotation": {
                        "version": "annotation-1.0",
                        "policy": "docs/annotation/ANNOTATION_GUIDELINE.md",
                    },
                    "quality_control": {
                        "annotator_a": True,
                        "annotator_b": True,
                        "adjudication": True,
                        "bbox_iou_mean": 0.81,
                    },
                    "images": metadata_images,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    return {
        "dataset_root": dataset_root,
        "dataset_yaml": dataset_yaml,
        "manifest_path": manifest_path,
        "image_ids": image_ids,
        "gt_by_image": gt_by_image,
    }


class FakeDetector:
    def __init__(
        self,
        gt_by_image: dict[str, list[tuple[str, tuple[float, float, float, float]]]],
        *,
        confidence: float = 0.90,
        extras: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.gt_by_image = gt_by_image
        self.confidence = confidence
        self.extras = extras or {}
        self.calls = 0

    def detect(self, image_path: str, image_id: str | None = None, **kwargs: Any) -> ImageDetectionResult:
        self.calls += 1
        detections = []
        for class_name, box in self.gt_by_image.get(image_id or "", ()):
            detections.append(
                DetectionRecord(
                    model_version="fake-serving",
                    image_id=image_id,
                    hazard_class=class_name,
                    confidence=self.confidence,
                    bbox_xyxy=[value * 640 for value in box],
                    bbox_norm=list(box),
                    status="detected",
                )
            )
        for extra in self.extras.get(image_id or "", ()):
            box = extra.get("bbox_norm", POTHOLE_BOX)
            detections.append(
                DetectionRecord(
                    model_version="fake-serving",
                    image_id=image_id,
                    hazard_class=extra.get("hazard_class", "pothole"),
                    confidence=extra.get("confidence", self.confidence),
                    bbox_xyxy=[value * 640 for value in box],
                    bbox_norm=list(box),
                    status=extra.get("status", "detected"),
                )
            )
        return ImageDetectionResult(
            model_version="fake-serving",
            pipeline_version="fake-pipeline",
            status=DetectionStatus.SUCCESS if detections else DetectionStatus.NO_DETECTIONS,
            image_id=image_id,
            detections=detections,
        )


class _FakeBoxMetrics:
    map = 1.0
    map50 = 1.0
    map75 = 1.0
    mp = 1.0
    mr = 1.0
    ap_class_index = [0, 1]
    ap50 = [1.0, 1.0]


class _FakeStageAResult:
    names = {0: "pothole", 1: "crack"}
    box = _FakeBoxMetrics()
    results_dict = {
        "metrics/precision(B)": 1.0,
        "metrics/recall(B)": 1.0,
        "metrics/mAP50(B)": 1.0,
        "metrics/mAP50-95(B)": 1.0,
    }


def _fake_stage_a(**kwargs: Any) -> _FakeStageAResult:
    return _FakeStageAResult()


class TestModelPreflight(unittest.TestCase):
    def test_missing_checkpoint_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = root / "models" / "missing" / "weights" / "best.pt"
            detection, severity = _write_configs(root, checkpoint)
            evaluator = IndependentEvaluator(
                workspace_root=root,
                detection_config=detection,
                severity_config=severity,
            )
            with self.assertRaises(ModelIntegrityError):
                evaluator.preflight()

    def test_smoke_marker_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = _build_checkpoint(root)
            (checkpoint.parent.parent / "P0_SMOKE_SUBSTITUTE.json").write_text(
                json.dumps({"status": "NON_PRODUCTION_P0_SMOKE_SUBSTITUTE"}),
                encoding="utf-8",
            )
            detection, severity = _write_configs(root, checkpoint)
            evaluator = IndependentEvaluator(
                workspace_root=root,
                detection_config=detection,
                severity_config=severity,
            )
            with self.assertRaises(SmokeSubstituteError):
                evaluator.preflight()

            allowed = IndependentEvaluator(
                workspace_root=root,
                detection_config=detection,
                severity_config=severity,
                allow_smoke_substitute=True,
            )
            preflight = allowed.preflight()
            self.assertTrue(preflight.harness_only)
            self.assertTrue(preflight.checkpoint.is_smoke_substitute)

    def test_confidence_contract_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = _build_checkpoint(root)
            detection, severity = _write_configs(
                root, checkpoint, conf=0.10, severity_conf=0.25
            )
            evaluator = IndependentEvaluator(
                workspace_root=root,
                detection_config=detection,
                severity_config=severity,
            )
            with self.assertRaises(ProductionParityError) as context:
                evaluator.preflight()
            self.assertIn("confidence contract", str(context.exception))

    def test_non_production_image_size_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = _build_checkpoint(root)
            detection, severity = _write_configs(root, checkpoint, imgsz=320)
            evaluator = IndependentEvaluator(
                workspace_root=root,
                detection_config=detection,
                severity_config=severity,
            )
            with self.assertRaises(ProductionParityError):
                evaluator.preflight()


class TestDatasetFailures(unittest.TestCase):
    def _evaluator(self, root: Path) -> IndependentEvaluator:
        checkpoint = _build_checkpoint(root)
        detection, severity = _write_configs(root, checkpoint)
        return IndependentEvaluator(
            workspace_root=root,
            detection_config=detection,
            severity_config=severity,
        )

    def test_empty_dataset_cannot_succeed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self._evaluator(root)
            data = _build_dataset(root, potholes=0, cracks=0, with_manifest=False)
            with self.assertRaises(EmptyDatasetError):
                evaluator.run(
                    data["dataset_yaml"],
                    run_stage_a=False,
                    run_stage_b=False,
                    run_route_replay=False,
                )

    def test_missing_annotation_is_not_silent_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self._evaluator(root)
            data = _build_dataset(root, potholes=2, cracks=0, with_manifest=False)
            (data["dataset_root"] / "labels" / "test" / "pothole_000.txt").unlink()
            with self.assertRaises(MissingAnnotationError):
                evaluator.run(
                    data["dataset_yaml"],
                    run_stage_a=False,
                    run_stage_b=False,
                    run_route_replay=False,
                )


class TestStageBFailures(unittest.TestCase):
    def _run_with_extras(self, root: Path, extras: dict[str, list[dict[str, Any]]]):
        data = _build_dataset(root, potholes=2, cracks=0, with_manifest=True)
        checkpoint = _build_checkpoint(root)
        detection, severity = _write_configs(root, checkpoint)
        evaluator = IndependentEvaluator(
            workspace_root=root,
            detection_config=detection,
            severity_config=severity,
        )
        detector = FakeDetector(data["gt_by_image"], extras=extras)
        return evaluator.run(
            data["dataset_yaml"],
            manifest_path=data["manifest_path"],
            detector=detector,
            run_stage_a=False,
            run_route_replay=False,
        )

    def test_unsupported_classes_are_excluded_and_disclosed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self._run_with_extras(
                root,
                {
                    "pothole_000": [
                        {
                            "hazard_class": "unsupported_class_2",
                            "status": "unsupported_class",
                            "bbox_norm": (0.6, 0.1, 0.8, 0.3),
                        }
                    ]
                },
            )
            self.assertEqual(report.stage_b["unsupported_detections_excluded"], 1)
            self.assertEqual(report.stage_b["invalid_detections"], 0)
            # Only supported potholes are counted as hazards.
            self.assertEqual(
                report.metrics["operational"]["per_class"]["pothole"]["predicted_count"], 2
            )

    def test_below_threshold_detection_fails_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self._run_with_extras(
                root,
                {
                    "pothole_000": [
                        {
                            "hazard_class": "pothole",
                            "confidence": 0.10,
                            "bbox_norm": (0.6, 0.1, 0.8, 0.3),
                        }
                    ]
                },
            )
            self.assertEqual(report.stage_b["below_threshold_detections"], 1)
            self.assertEqual(
                report.gate("production_parity").status, EvaluationStatus.FAIL
            )
            self.assertEqual(report.status, EvaluationStatus.FAIL)

    def test_invalid_prediction_box_fails_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self._run_with_extras(
                root,
                {
                    "pothole_000": [
                        {
                            "hazard_class": "pothole",
                            "bbox_norm": (0.6, 0.2, 0.4, 0.9),
                        }
                    ]
                },
            )
            self.assertEqual(report.stage_b["invalid_detections"], 1)
            self.assertEqual(
                report.gate("production_parity").status, EvaluationStatus.FAIL
            )

    def test_missing_class_is_reported_as_insufficient_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _build_dataset(root, potholes=30, cracks=0, with_manifest=True)
            checkpoint = _build_checkpoint(root)
            detection, severity = _write_configs(root, checkpoint)
            evaluator = IndependentEvaluator(
                workspace_root=root,
                detection_config=detection,
                severity_config=severity,
            )
            report = evaluator.run(
                data["dataset_yaml"],
                manifest_path=data["manifest_path"],
                detector=FakeDetector(data["gt_by_image"]),
                run_stage_a=False,
                run_route_replay=False,
                reference_session_ids={"reference-session-alpha"},
            )
            self.assertNotEqual(report.status, EvaluationStatus.PASS)
            gate = report.gate("metric_completeness")
            self.assertEqual(gate.status, EvaluationStatus.CONDITIONAL)
            self.assertIn("crack", gate.evidence["insufficient_classes"])

    def test_harness_only_smoke_run_is_never_not_assessed_as_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _build_dataset(root, potholes=2, cracks=0, with_manifest=True)
            checkpoint = _build_checkpoint(root)
            (checkpoint.parent.parent / "P0_SMOKE_SUBSTITUTE.json").write_text(
                json.dumps({"status": "NON_PRODUCTION_P0_SMOKE_SUBSTITUTE"}),
                encoding="utf-8",
            )
            detection, severity = _write_configs(root, checkpoint)
            evaluator = IndependentEvaluator(
                workspace_root=root,
                detection_config=detection,
                severity_config=severity,
                allow_smoke_substitute=True,
            )
            report = evaluator.run(
                data["dataset_yaml"],
                manifest_path=data["manifest_path"],
                detector=FakeDetector(data["gt_by_image"]),
                run_stage_a=False,
                run_route_replay=False,
            )
            self.assertTrue(report.harness_only)
            self.assertEqual(report.status, EvaluationStatus.NOT_ASSESSED)


class TestPerfectEvaluation(unittest.TestCase):
    def test_all_gates_can_pass_with_complete_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _build_dataset(root, potholes=30, cracks=30, with_manifest=True)
            checkpoint = _build_checkpoint(root)
            detection, severity = _write_configs(root, checkpoint)
            evaluator = IndependentEvaluator(
                workspace_root=root,
                detection_config=detection,
                severity_config=severity,
            )
            before_checkpoint = compute_file_sha256(checkpoint)
            before_detection = compute_file_sha256(detection)
            before_severity = compute_file_sha256(severity)

            report = evaluator.run(
                data["dataset_yaml"],
                manifest_path=data["manifest_path"],
                detector=FakeDetector(data["gt_by_image"]),
                stage_a_runner=_fake_stage_a,
                run_route_replay=True,
                reference_session_ids={"reference-session-alpha"},
            )

            self.assertEqual(report.status, EvaluationStatus.PASS, report.to_dict())
            self.assertEqual(
                {gate.gate: gate.status for gate in report.gates},
                {
                    "dataset_independence": EvaluationStatus.PASS,
                    "annotation_reliability": EvaluationStatus.PASS,
                    "reproducibility": EvaluationStatus.PASS,
                    "metric_completeness": EvaluationStatus.PASS,
                    "production_parity": EvaluationStatus.PASS,
                    "decision_impact": EvaluationStatus.PASS,
                    "safety_honesty": EvaluationStatus.PASS,
                },
            )
            self.assertAlmostEqual(report.metrics["ap"]["map50"], 1.0)
            self.assertAlmostEqual(
                report.metrics["ap"]["per_class"]["pothole"]["ap50"], 1.0
            )
            self.assertAlmostEqual(
                report.metrics["ap"]["per_class"]["crack"]["ap50"], 1.0
            )
            self.assertIsNotNone(report.route_replay)
            self.assertTrue(report.route_replay["enough_evidence"])

            # Evaluation must not modify the serving checkpoint or config.
            self.assertEqual(compute_file_sha256(checkpoint), before_checkpoint)
            self.assertEqual(compute_file_sha256(detection), before_detection)
            self.assertEqual(compute_file_sha256(severity), before_severity)
            self.assertFalse(report.artifacts["mutation_detected"])
            self.assertFalse(report.artifacts["production_scoring_modified"])

    def test_empty_label_is_scored_as_negative_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = _build_dataset(root, potholes=1, cracks=0, with_manifest=True)
            # Empty label file for one additional image = verified negative.
            images_dir = data["dataset_root"] / "images" / "test"
            labels_dir = data["dataset_root"] / "labels" / "test"
            assert cv2.imwrite(str(images_dir / "negative.jpg"), _pattern_image(99))
            (labels_dir / "negative.txt").write_text("", encoding="utf-8")
            manifest = json.loads(data["manifest_path"].read_text(encoding="utf-8"))
            manifest["images"].append(
                {
                    "image_id": "negative",
                    "file": "images/test/negative.jpg",
                    "session_id": "independent-session-9",
                    "condition": "daylight",
                    "route_id": "route-9",
                    "segment_id": "segment-9",
                }
            )
            data["manifest_path"].write_text(json.dumps(manifest), encoding="utf-8")

            checkpoint = _build_checkpoint(root)
            detection, severity = _write_configs(root, checkpoint)
            evaluator = IndependentEvaluator(
                workspace_root=root,
                detection_config=detection,
                severity_config=severity,
            )
            report = evaluator.run(
                data["dataset_yaml"],
                manifest_path=data["manifest_path"],
                detector=FakeDetector(data["gt_by_image"]),
                run_stage_a=False,
                run_route_replay=False,
            )
            self.assertEqual(report.dataset["negative_image_count"], 1)
            self.assertEqual(report.dataset["ground_truth_count"], 1)
            # One clean negative image cannot produce an FP.
            self.assertEqual(
                report.metrics["operational"]["overall"]["false_positives"], 0
            )


if __name__ == "__main__":
    unittest.main()
