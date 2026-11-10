"""SafeRoute AI — Phase 42 independent evaluation orchestrator.

Stage A runs the official Ultralytics validator on the independent split.
Stage B runs the **actual production detection pipeline** (preprocess-v1 ->
serving checkpoint -> detection record -> normalized box). Stage B is
authoritative for operational precision/recall at the configured threshold.

Hard safety rules enforced here:
* The configured serving checkpoint must exist; no silent fallback.
* The P0 smoke substitute is refused for real evaluation.
* Production config values are asserted, including the single confidence
  contract between ``detection.yaml`` and ``hazard_severity.yaml``.
* Missing annotations and empty datasets are hard failures.
* Unsupported classes are excluded and disclosed, never counted as hazards.
* The checkpoint/config files are hashed before and after; mutation fails the
  run.
"""

from __future__ import annotations

import json
import math
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml

from .confidence_intervals import (
    DEFAULT_MIN_SAMPLES,
    BootstrapCI,
    clustered_bootstrap_ci,
    insufficient_sample,
    wilson_interval,
)
from .dataset_validation import (
    DatasetInventory,
    DatasetValidationError,
    EmptyDatasetError,
    collect_dataset,
    compute_file_sha256,
    summarise_inventory,
)
from .leakage import LeakageReport, analyze_leakage
from .matching import (
    IOU_THRESHOLDS,
    DatasetMatch,
    GroundTruthBox,
    PredictionBox,
    match_dataset,
    validate_bbox_norm,
)
from .metrics import (
    APMetrics,
    compute_ap_metrics,
    compute_counts,
    deduplicate_frame_false_positives,
    group_metrics,
    operational_summary,
)
from .route_replay import RouteReplayError, RouteReplayReport, replay_routes

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DETECTION_CONFIG = "config/detection.yaml"
DEFAULT_SEVERITY_CONFIG = "config/hazard_severity.yaml"
SMOKE_MARKER = "P0_SMOKE_SUBSTITUTE.json"

REQUIRED_IMGSZ = 640
REQUIRED_CONF = 0.25
REQUIRED_IOU = 0.45
REQUIRED_MAX_DET = 300
REQUIRED_CLASSES: Mapping[int, str] = {0: "pothole", 1: "crack"}
STAGE_A_AP_TOLERANCE = 0.25


class EvaluationStatus(str, Enum):
    PASS = "PASS"
    CONDITIONAL = "CONDITIONAL"
    FAIL = "FAIL"
    NOT_ASSESSED = "NOT_ASSESSED"


class EvaluationError(Exception):
    """Base class for Phase 42 evaluation failures."""


class ModelIntegrityError(EvaluationError):
    """The configured serving checkpoint is missing or unusable."""


class SmokeSubstituteError(ModelIntegrityError):
    """The checkpoint is the non-production P0 smoke substitute."""


class ProductionParityError(EvaluationError):
    """The evaluation configuration does not match the production contract."""


class EvaluationRunError(EvaluationError):
    """Inference or metric computation failed."""


# ---------------------------------------------------------------------------
# Production configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InferenceConfig:
    detection_config_path: Path
    severity_config_path: Path
    detection_config_sha256: str
    severity_config_sha256: str
    model_version: str
    checkpoint: Path
    checkpoint_rel: str
    imgsz: int
    conf: float
    iou: float
    max_det: int
    supported_classes: Mapping[int, str]
    unsupported_classes: Tuple[str, ...]
    severity_confidence_threshold: float

    def parity_issues(self) -> List[str]:
        issues: List[str] = []
        if not math.isfinite(self.conf):
            issues.append("inference.conf is missing or non-finite")
        if not math.isfinite(self.iou):
            issues.append("inference.iou is missing or non-finite")
        if not math.isfinite(self.severity_confidence_threshold):
            issues.append("hazard_severity thresholds.confidence_threshold is missing")
        if self.imgsz != REQUIRED_IMGSZ:
            issues.append(f"imgsz={self.imgsz} (required {REQUIRED_IMGSZ})")
        if math.isfinite(self.conf) and abs(self.conf - REQUIRED_CONF) > 1e-9:
            issues.append(f"inference.conf={self.conf} (required {REQUIRED_CONF})")
        if math.isfinite(self.iou) and abs(self.iou - REQUIRED_IOU) > 1e-9:
            issues.append(f"inference.iou={self.iou} (required {REQUIRED_IOU})")
        if self.max_det != REQUIRED_MAX_DET:
            issues.append(f"max_det={self.max_det} (required {REQUIRED_MAX_DET})")
        if (
            math.isfinite(self.conf)
            and math.isfinite(self.severity_confidence_threshold)
            and abs(self.conf - self.severity_confidence_threshold) > 1e-9
        ):
            issues.append(
                "confidence contract broken: detection.yaml inference.conf="
                f"{self.conf} != hazard_severity.yaml thresholds.confidence_threshold="
                f"{self.severity_confidence_threshold}"
            )
        if dict(self.supported_classes) != dict(REQUIRED_CLASSES):
            issues.append(
                f"supported_classes={dict(self.supported_classes)} "
                f"(required {dict(REQUIRED_CLASSES)})"
            )
        if not str(self.checkpoint_rel).strip():
            issues.append("model.checkpoint is empty")
        return issues

    def to_dict(self) -> Dict[str, object]:
        return {
            "detection_config_path": str(self.detection_config_path),
            "severity_config_path": str(self.severity_config_path),
            "detection_config_sha256": self.detection_config_sha256,
            "severity_config_sha256": self.severity_config_sha256,
            "model_version": self.model_version,
            "checkpoint": str(self.checkpoint),
            "checkpoint_rel": self.checkpoint_rel,
            "imgsz": self.imgsz,
            "conf": self.conf,
            "iou": self.iou,
            "max_det": self.max_det,
            "supported_classes": {str(key): value for key, value in self.supported_classes.items()},
            "unsupported_classes": list(self.unsupported_classes),
            "severity_confidence_threshold": self.severity_confidence_threshold,
        }


def _read_yaml_bytes(path: Path, label: str) -> Tuple[bytes, Mapping[str, Any]]:
    if not path.is_file():
        raise ProductionParityError(f"{label} not found at {path}")
    raw = path.read_bytes()
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ProductionParityError(f"Invalid {label} at {path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ProductionParityError(f"{label} at {path} must contain a mapping")
    return raw, data


def load_production_config(
    workspace_root: Optional[Path] = None,
    detection_config: Optional[Path] = None,
    severity_config: Optional[Path] = None,
) -> InferenceConfig:
    """Load and assert the production inference contract."""
    workspace = Path(workspace_root).resolve() if workspace_root else WORKSPACE_ROOT
    detection_path = (
        Path(detection_config).resolve()
        if detection_config
        else (workspace / DEFAULT_DETECTION_CONFIG).resolve()
    )
    severity_path = (
        Path(severity_config).resolve()
        if severity_config
        else (workspace / DEFAULT_SEVERITY_CONFIG).resolve()
    )

    detection_raw, detection = _read_yaml_bytes(detection_path, "detection config")
    severity_raw, severity = _read_yaml_bytes(severity_path, "severity config")

    inference = detection.get("inference") or {}
    model_cfg = detection.get("model") or {}
    metadata = detection.get("metadata") or {}
    raw_supported = detection.get("supported_classes") or {}
    supported = {int(key): str(value) for key, value in raw_supported.items()}
    unsupported_raw = detection.get("unsupported_classes") or []
    unsupported = tuple(str(value) for value in unsupported_raw)

    checkpoint_rel = str(model_cfg.get("checkpoint") or "").strip()
    checkpoint = (
        (workspace / checkpoint_rel).resolve() if checkpoint_rel else (workspace / "__missing__")
    )
    severity_threshold = float(
        (severity.get("thresholds") or {}).get("confidence_threshold", float("nan"))
    )

    config = InferenceConfig(
        detection_config_path=detection_path,
        severity_config_path=severity_path,
        detection_config_sha256=compute_file_sha256(detection_path),
        severity_config_sha256=compute_file_sha256(severity_path),
        model_version=str(metadata.get("model_version", "unknown")),
        checkpoint=checkpoint,
        checkpoint_rel=checkpoint_rel,
        imgsz=int(inference.get("imgsz", 0)),
        conf=float(inference.get("conf", float("nan"))),
        iou=float(inference.get("iou", float("nan"))),
        max_det=int(inference.get("max_det", 0)),
        supported_classes=supported,
        unsupported_classes=unsupported,
        severity_confidence_threshold=severity_threshold,
    )
    issues = config.parity_issues()
    if issues:
        raise ProductionParityError(
            "Evaluation refuses to run with a non-production inference contract:\n- "
            + "\n- ".join(issues)
        )
    return config


# ---------------------------------------------------------------------------
# Checkpoint identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckpointIdentity:
    path: Path
    exists: bool
    sha256: Optional[str]
    size_bytes: int
    marker_path: Optional[Path]
    marker: Mapping[str, Any]
    is_smoke_substitute: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": str(self.path),
            "exists": self.exists,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "marker_path": str(self.marker_path) if self.marker_path else None,
            "marker_status": self.marker.get("status") if self.marker else None,
            "is_smoke_substitute": self.is_smoke_substitute,
        }


def identify_checkpoint(path: Path) -> CheckpointIdentity:
    """Hash a checkpoint and detect the P0 smoke-substitute marker."""
    checkpoint = Path(path).resolve()
    if not checkpoint.is_file():
        return CheckpointIdentity(
            path=checkpoint,
            exists=False,
            sha256=None,
            size_bytes=0,
            marker_path=None,
            marker={},
            is_smoke_substitute=False,
        )

    sha256 = compute_file_sha256(checkpoint)
    marker_candidates: List[Path] = []
    model_dir = checkpoint.parent.parent
    for directory in (checkpoint.parent, model_dir):
        marker_candidates.extend(sorted(directory.glob("*SUBSTITUTE*.json")))
        exact = directory / SMOKE_MARKER
        if exact.is_file():
            marker_candidates.append(exact)

    marker_path: Optional[Path] = None
    marker: Mapping[str, Any] = {}
    for candidate in marker_candidates:
        if not candidate.is_file():
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            data = {"status": "UNREADABLE_MARKER"}
        marker_path = candidate
        marker = data if isinstance(data, Mapping) else {}
        break

    is_smoke = marker_path is not None
    if "p0-smoke" in {part.lower() for part in checkpoint.parts}:
        is_smoke = True
    marker_sha = marker.get("installed_sha256") or marker.get("source_sha256")
    if marker_sha and str(marker_sha).upper() == sha256.upper():
        is_smoke = True

    return CheckpointIdentity(
        path=checkpoint,
        exists=True,
        sha256=sha256,
        size_bytes=checkpoint.stat().st_size,
        marker_path=marker_path,
        marker=marker,
        is_smoke_substitute=is_smoke,
    )


def _environment() -> Dict[str, Any]:
    environment: Dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    for module_name in ("torch", "ultralytics", "cv2", "numpy"):
        try:
            module = __import__(module_name)
            environment[module_name] = getattr(module, "__version__", "unknown")
        except Exception:  # pragma: no cover - optional diagnostic
            environment[module_name] = "unavailable"
    try:
        import torch

        environment["cuda_available"] = bool(torch.cuda.is_available())
        environment["cuda_device"] = (
            torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        )
    except Exception:  # pragma: no cover - optional diagnostic
        environment["cuda_available"] = False
        environment["cuda_device"] = None
    return environment


@dataclass(frozen=True)
class PreflightReport:
    config: InferenceConfig
    checkpoint: CheckpointIdentity
    harness_only: bool
    warnings: Tuple[str, ...]
    environment: Mapping[str, Any]

    def to_dict(self) -> Dict[str, object]:
        return {
            "config": self.config.to_dict(),
            "checkpoint": self.checkpoint.to_dict(),
            "harness_only": self.harness_only,
            "warnings": list(self.warnings),
            "environment": dict(self.environment),
        }


# ---------------------------------------------------------------------------
# Stage A
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageAResult:
    ran: bool
    metrics: Mapping[str, Any]
    per_class_ap50: Mapping[str, float]
    caveat: str
    error: Optional[str] = None
    command: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "ran": self.ran,
            "metrics": dict(self.metrics),
            "per_class_ap50": dict(self.per_class_ap50),
            "caveat": self.caveat,
            "error": self.error,
            "command": dict(self.command),
        }


def _extract_stage_a_metrics(raw: Any) -> Tuple[Dict[str, Any], Dict[str, float]]:
    metrics: Dict[str, Any] = {}
    per_class: Dict[str, float] = {}

    results_dict = getattr(raw, "results_dict", None)
    if isinstance(results_dict, Mapping):
        metrics["results_dict"] = {
            str(key): float(value)
            for key, value in results_dict.items()
            if isinstance(value, (int, float))
        }

    box = getattr(raw, "box", None)
    for attribute in ("map", "map50", "map75", "mp", "mr"):
        value = getattr(box, attribute, None)
        if isinstance(value, (int, float)):
            metrics[attribute] = float(value)

    names = getattr(raw, "names", {}) or {}
    if isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
        names = {index: value for index, value in enumerate(names)}

    ap_class_index = getattr(box, "ap_class_index", None)
    ap50_vector = getattr(box, "ap50", None)
    if ap50_vector is None:
        ap50_vector = getattr(box, "ap50_95", None)
    if ap_class_index is not None and ap50_vector is not None:
        try:
            indices = list(ap_class_index)
            values = list(ap50_vector)
            for position, class_index in enumerate(indices):
                if position >= len(values):
                    break
                class_name = str(names.get(int(class_index), class_index))
                per_class[class_name] = float(values[position])
        except (TypeError, ValueError):
            per_class = {}

    return metrics, per_class


@dataclass(frozen=True)
class FalsePositiveObservation:
    session_id: Optional[str]
    class_name: str
    bbox_norm: Tuple[float, float, float, float]


@dataclass
class StageBResult:
    ran: bool
    predictions_by_image: Dict[str, Tuple[PredictionBox, ...]]
    images_inferred: int
    images_failed: int
    failed_image_ids: Tuple[str, ...]
    failed_reasons: Mapping[str, str]
    unsupported_detections_excluded: int
    below_threshold_detections: int
    invalid_detections: int
    total_detections: int
    coordinate_mode: str
    inference_ms: float
    caveat: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, object]:
        return {
            "ran": self.ran,
            "images_inferred": self.images_inferred,
            "images_failed": self.images_failed,
            "failed_image_ids": list(self.failed_image_ids),
            "failed_reasons": dict(self.failed_reasons),
            "prediction_count": sum(len(value) for value in self.predictions_by_image.values()),
            "images_with_predictions": sum(
                1 for value in self.predictions_by_image.values() if value
            ),
            "unsupported_detections_excluded": self.unsupported_detections_excluded,
            "below_threshold_detections": self.below_threshold_detections,
            "invalid_detections": self.invalid_detections,
            "total_detections": self.total_detections,
            "coordinate_mode": self.coordinate_mode,
            "inference_ms": self.inference_ms,
            "caveat": list(self.caveat),
        }


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: EvaluationStatus
    detail: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "gate": self.gate,
            "status": self.status.value,
            "detail": self.detail,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class EvaluationReport:
    status: EvaluationStatus
    harness_only: bool
    gates: Tuple[GateResult, ...]
    preflight: PreflightReport
    dataset: Mapping[str, Any]
    leakage: Mapping[str, Any]
    stage_a: Mapping[str, Any]
    stage_b: Mapping[str, Any]
    metrics: Mapping[str, Any]
    route_replay: Optional[Mapping[str, Any]]
    caveats: Tuple[str, ...]
    safety_note: str
    generated_utc: str
    artifacts: Mapping[str, Any]

    def gate(self, name: str) -> Optional[GateResult]:
        for gate in self.gates:
            if gate.gate == name:
                return gate
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": "PHASE_42",
            "status": self.status.value,
            "harness_only": self.harness_only,
            "gates": [gate.to_dict() for gate in self.gates],
            "preflight": self.preflight.to_dict(),
            "dataset": dict(self.dataset),
            "leakage": dict(self.leakage),
            "stage_a": dict(self.stage_a),
            "stage_b": dict(self.stage_b),
            "metrics": dict(self.metrics),
            "route_replay": dict(self.route_replay) if self.route_replay else None,
            "caveats": list(self.caveats),
            "safety_note": self.safety_note,
            "generated_utc": self.generated_utc,
            "artifacts": dict(self.artifacts),
        }

    def write_json(self, path: Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=False),
            encoding="utf-8",
        )
        return destination


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class IndependentEvaluator:
    """Run Phase 42 Stage A + Stage B evaluation and acceptance gates."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        *,
        detection_config: Optional[Path] = None,
        severity_config: Optional[Path] = None,
        allow_smoke_substitute: bool = False,
    ) -> None:
        self.workspace_root = (
            Path(workspace_root).resolve() if workspace_root else WORKSPACE_ROOT
        )
        self.detection_config = detection_config
        self.severity_config = severity_config
        self.allow_smoke_substitute = bool(allow_smoke_substitute)

    # -- preflight ---------------------------------------------------------

    def preflight(self) -> PreflightReport:
        config = load_production_config(
            self.workspace_root, self.detection_config, self.severity_config
        )
        checkpoint = identify_checkpoint(config.checkpoint)
        if not checkpoint.exists:
            raise ModelIntegrityError(
                "Approved serving checkpoint is missing: "
                f"'{config.checkpoint}'. Phase 42 refuses to substitute YOLO11 "
                "pretrained weights, the v1 checkpoint, a newly trained model, or a "
                "similarly named file."
            )

        warnings: List[str] = []
        harness_only = False
        if checkpoint.is_smoke_substitute:
            if not self.allow_smoke_substitute:
                raise SmokeSubstituteError(
                    "The configured checkpoint is the non-production P0 smoke "
                    f"substitute (marker: {checkpoint.marker_path}). An independent "
                    "v2 evaluation cannot be reported from it. Restore the genuine "
                    "saferoute-yolo11-v2 checkpoint, or pass allow_smoke_substitute "
                    "for an explicitly harness-only run."
                )
            harness_only = True
            warnings.append(
                "HARNESS-ONLY: the configured checkpoint is the P0 smoke substitute. "
                "Any resulting metrics describe the smoke model, not the real "
                "saferoute-yolo11-v2 serving model."
            )
        if checkpoint.marker_path and not checkpoint.is_smoke_substitute:
            warnings.append(
                f"A marker JSON exists beside the checkpoint ({checkpoint.marker_path}) "
                "but does not identify the file as the smoke substitute."
            )

        return PreflightReport(
            config=config,
            checkpoint=checkpoint,
            harness_only=harness_only,
            warnings=tuple(warnings),
            environment=_environment(),
        )

    def _artifact_snapshot(self, preflight: PreflightReport) -> Dict[str, Any]:
        config = preflight.config
        checkpoint = identify_checkpoint(config.checkpoint)
        return {
            "checkpoint_sha256": checkpoint.sha256,
            "checkpoint_size_bytes": checkpoint.size_bytes,
            "detection_config_sha256": compute_file_sha256(config.detection_config_path),
            "severity_config_sha256": compute_file_sha256(config.severity_config_path),
        }

    # -- Stage A -----------------------------------------------------------

    def run_stage_a(
        self,
        dataset_yaml: Path,
        preflight: PreflightReport,
        *,
        split: str = "test",
        runner: Optional[Callable[..., Any]] = None,
    ) -> StageAResult:
        config = preflight.config
        caveat = (
            "Ultralytics validation is not assumed to apply confidence filtering and "
            "NMS identically to serving. In particular, passing conf to val can filter "
            "predictions before AP accumulation, so Stage A AP is not directly "
            "comparable to the operational 0.25 working point. Stage B is authoritative."
        )
        command = {
            "data": str(dataset_yaml),
            "imgsz": config.imgsz,
            "conf": config.conf,
            "iou": config.iou,
            "max_det": config.max_det,
            "split": split,
        }
        try:
            if runner is not None:
                raw = runner(**command, checkpoint=str(config.checkpoint))
            else:
                from ultralytics import YOLO

                model = YOLO(str(config.checkpoint))
                raw = model.val(
                    data=str(dataset_yaml),
                    imgsz=config.imgsz,
                    conf=config.conf,
                    iou=config.iou,
                    max_det=config.max_det,
                    split=split,
                    project=str(self.workspace_root / "reports" / "phase42_stage_a"),
                    name="independent",
                    exist_ok=True,
                    plots=False,
                    verbose=False,
                )
            metrics, per_class = _extract_stage_a_metrics(raw)
            return StageAResult(
                ran=True,
                metrics=metrics,
                per_class_ap50=per_class,
                caveat=caveat,
                command=command,
            )
        except Exception as exc:  # noqa: BLE001 - Stage A failure must be reported
            return StageAResult(
                ran=False,
                metrics={},
                per_class_ap50={},
                caveat=caveat,
                error=f"{type(exc).__name__}: {exc}",
                command=command,
            )

    # -- Stage B -----------------------------------------------------------

    def run_stage_b(
        self,
        inventory: DatasetInventory,
        preflight: PreflightReport,
        *,
        detector: Optional[Any] = None,
    ) -> StageBResult:
        config = preflight.config
        if detector is None:
            try:
                from src.detection.detector import HazardDetector

                detector = HazardDetector(workspace_root=self.workspace_root)
            except Exception as exc:  # noqa: BLE001
                raise EvaluationRunError(
                    f"Could not construct the production detector: {type(exc).__name__}: {exc}"
                ) from exc

        supported_names = set(config.supported_classes.values())
        predictions_by_image: Dict[str, Tuple[PredictionBox, ...]] = {}
        failed_ids: List[str] = []
        failed_reasons: Dict[str, str] = {}
        unsupported = 0
        below_threshold = 0
        invalid = 0
        total_detections = 0
        start = datetime.now(timezone.utc)

        for image in inventory.images:
            try:
                result = detector.detect(
                    str(image.image_path),
                    image_id=image.image_id,
                    route_id=image.route_id,
                    segment_id=image.segment_id,
                )
            except Exception as exc:  # noqa: BLE001 - one bad image must be disclosed
                failed_ids.append(image.image_id)
                failed_reasons[image.image_id] = f"{type(exc).__name__}: {exc}"
                continue

            status = getattr(result, "status", None)
            status_value = getattr(status, "value", status)
            if status_value not in ("success", "no_detections"):
                failed_ids.append(image.image_id)
                failed_reasons[image.image_id] = str(
                    getattr(result, "error", None) or f"detection status={status_value}"
                )
                continue

            accepted: List[PredictionBox] = []
            for detection in getattr(result, "detections", ()) or ():
                total_detections += 1
                try:
                    confidence = float(detection.confidence)
                except (TypeError, ValueError):
                    invalid += 1
                    continue
                if not (0.0 <= confidence <= 1.0):
                    invalid += 1
                    continue
                if confidence < config.conf:
                    below_threshold += 1
                    continue

                hazard_class = str(getattr(detection, "hazard_class", "") or "")
                detection_status = getattr(detection, "status", "detected")
                if (
                    detection_status == "unsupported_class"
                    or hazard_class.startswith("unsupported_class")
                    or hazard_class not in supported_names
                ):
                    unsupported += 1
                    continue

                try:
                    bbox = validate_bbox_norm(
                        getattr(detection, "bbox_norm", None),
                        label=f"{image.image_id}:{hazard_class}",
                    )
                except ValueError:
                    invalid += 1
                    continue
                accepted.append(
                    PredictionBox(
                        image_id=image.image_id,
                        class_name=hazard_class,
                        confidence=confidence,
                        bbox_norm=bbox,
                        status="detected",
                    )
                )
            predictions_by_image[image.image_id] = tuple(accepted)

        elapsed_ms = (
            datetime.now(timezone.utc) - start
        ).total_seconds() * 1000.0

        caveat = (
            "Stage B uses the production pipeline and its normalized "
            "original-image boxes. Unsupported classes are excluded and disclosed; "
            "they are never counted as trained hazards.",
            "Raw per-frame predictions are evaluated; within-image aggregator "
            "de-duplication is not applied to detector accuracy metrics.",
        )

        return StageBResult(
            ran=True,
            predictions_by_image=predictions_by_image,
            images_inferred=len(inventory.images) - len(failed_ids),
            images_failed=len(failed_ids),
            failed_image_ids=tuple(sorted(failed_ids)),
            failed_reasons=failed_reasons,
            unsupported_detections_excluded=unsupported,
            below_threshold_detections=below_threshold,
            invalid_detections=invalid,
            total_detections=total_detections,
            coordinate_mode="bbox_norm_original_image",
            inference_ms=elapsed_ms,
            caveat=caveat,
        )

    # -- metrics -----------------------------------------------------------

    def _compute_metrics(
        self,
        inventory: DatasetInventory,
        stage_b: StageBResult,
        config: InferenceConfig,
        *,
        min_class_samples: int,
    ) -> Dict[str, Any]:
        class_names = list(config.supported_classes.values())
        failed = set(stage_b.failed_image_ids)
        evaluated_ids = {
            image.image_id for image in inventory.images if image.image_id not in failed
        }
        gt_by_image_all = inventory.ground_truth_by_image()
        gt_by_image = {image_id: gt_by_image_all[image_id] for image_id in evaluated_ids}
        preds = {
            image_id: stage_b.predictions_by_image.get(image_id, ())
            for image_id in evaluated_ids
        }

        matches: Dict[float, DatasetMatch] = {}
        for threshold in IOU_THRESHOLDS:
            matches[threshold] = match_dataset(
                preds, gt_by_image, evaluated_ids, threshold, class_names
            )

        ap = compute_ap_metrics(matches, class_names)
        operational = operational_summary(
            matches[0.50], inventory.total_distance_km, class_names
        )

        image_map = inventory.image_by_id()
        groups = group_metrics(
            preds,
            gt_by_image,
            {
                image_id: image_map[image_id].condition
                for image_id in evaluated_ids
            },
            evaluated_ids,
            class_names,
        )

        session_by_image = {
            image_id: (image_map[image_id].session_id or image_id)
            for image_id in evaluated_ids
        }
        operational_match = matches[0.50]

        @dataclass(frozen=True)
        class _Bernoulli:
            cluster_id: str
            success: int

        def _proportion(items: Sequence["_Bernoulli"]) -> Optional[float]:
            if not items:
                return None
            return float(sum(item.success for item in items)) / float(len(items))

        uncertainty: Dict[str, Any] = {"precision": {}, "recall": {}}
        for class_name in class_names:
            class_predictions = [
                prediction
                for prediction in operational_match.scored_predictions
                if prediction.class_name == class_name
            ]
            precision_observations = [
                _Bernoulli(
                    cluster_id=session_by_image.get(prediction.image_id, prediction.image_id),
                    success=1 if prediction.is_true_positive else 0,
                )
                for prediction in class_predictions
            ]
            matched_gt = [
                prediction.matched_gt
                for prediction in class_predictions
                if prediction.is_true_positive and prediction.matched_gt is not None
            ]
            false_negatives = [
                box for box in operational_match.false_negatives if box.class_name == class_name
            ]
            recall_observations = [
                _Bernoulli(
                    cluster_id=(
                        getattr(box, "session_id", None)
                        or (box.image_id if box is not None else "unknown")
                    ),
                    success=1,
                )
                for box in matched_gt
            ] + [
                _Bernoulli(
                    cluster_id=(
                        getattr(box, "session_id", None) or box.image_id or "unknown"
                    ),
                    success=0,
                )
                for box in false_negatives
            ]

            summary = operational_match.per_class.get(class_name)
            tp = summary.true_positives if summary else 0
            fp = summary.false_positives if summary else 0
            gt_count = summary.ground_truth_count if summary else 0
            predicted_count = tp + fp

            precision_ci: BootstrapCI = clustered_bootstrap_ci(
                precision_observations, _proportion, seed=42
            )
            recall_ci: BootstrapCI = clustered_bootstrap_ci(
                recall_observations, _proportion, seed=42
            )
            status = (
                "ok"
                if not insufficient_sample(gt_count, min_class_samples)
                and not insufficient_sample(predicted_count, min_class_samples)
                else "insufficient_sample"
            )
            uncertainty["precision"][class_name] = {
                "count": predicted_count,
                "successes": tp,
                "wilson_95": wilson_interval(tp, predicted_count),
                "bootstrap": precision_ci.to_dict(),
                "status": status,
            }
            uncertainty["recall"][class_name] = {
                "count": gt_count,
                "successes": tp,
                "wilson_95": wilson_interval(tp, gt_count),
                "bootstrap": recall_ci.to_dict(),
                "status": status,
            }

        all_precision_observations = [
            _Bernoulli(
                cluster_id=session_by_image.get(prediction.image_id, prediction.image_id),
                success=1 if prediction.is_true_positive else 0,
            )
            for prediction in operational_match.scored_predictions
        ]
        all_recall_observations = [
            _Bernoulli(
                cluster_id=(
                    getattr(prediction.matched_gt, "session_id", None)
                    or prediction.image_id
                ),
                success=1,
            )
            for prediction in operational_match.scored_predictions
            if prediction.is_true_positive and prediction.matched_gt is not None
        ] + [
            _Bernoulli(
                cluster_id=(getattr(box, "session_id", None) or box.image_id or "unknown"),
                success=0,
            )
            for box in operational_match.false_negatives
        ]
        overall_summary = operational["overall"]
        uncertainty["overall"] = {
            "precision": {
                "count": overall_summary["predicted_count"],
                "successes": overall_summary["true_positives"],
                "wilson_95": wilson_interval(
                    overall_summary["true_positives"], overall_summary["predicted_count"]
                ),
                "bootstrap": clustered_bootstrap_ci(
                    all_precision_observations, _proportion, seed=42
                ).to_dict(),
            },
            "recall": {
                "count": overall_summary["ground_truth_count"],
                "successes": overall_summary["true_positives"],
                "wilson_95": wilson_interval(
                    overall_summary["true_positives"],
                    overall_summary["ground_truth_count"],
                ),
                "bootstrap": clustered_bootstrap_ci(
                    all_recall_observations, _proportion, seed=42
                ).to_dict(),
            },
            "min_class_samples": min_class_samples,
            "method_note": (
                "Bootstrap resamples collection sessions, not frames. Wilson intervals "
                "treat boxes/predictions as Bernoulli units; both are reported so the "
                "clustering assumption is visible."
            ),
        }

        false_positive_observations = [
            FalsePositiveObservation(
                session_id=session_by_image.get(prediction.image_id),
                class_name=prediction.class_name,
                bbox_norm=prediction.bbox_norm,
            )
            for prediction in operational_match.scored_predictions
            if not prediction.is_true_positive and prediction.bbox_norm is not None
        ]

        raw_fp = operational_match.false_positives
        dedup_fp = deduplicate_frame_false_positives(false_positive_observations)
        distance_km = inventory.total_distance_km
        dedup = {
            "raw_frame_false_positives": raw_fp,
            "frame_deduplicated_false_positives": dedup_fp,
            "deduplication_method": (
                "heuristic: same session+class and normalized box centre within 0.15; "
                "unknown sessions are never merged"
            ),
            "raw_false_positives_per_km": (
                raw_fp / distance_km if distance_km and distance_km > 0 else None
            ),
            "deduplicated_false_positives_per_km": (
                dedup_fp / distance_km if distance_km and distance_km > 0 else None
            ),
            "distance_km": distance_km,
            "caveat": (
                "Adjacent video frames are not independent road observations. FP/km is "
                "reported only when verified distance is present, and the deduplicated "
                "count is explicitly heuristic."
            ),
        }

        coverage = {
            "images_total": inventory.image_count,
            "images_inferred": stage_b.images_inferred,
            "images_failed": stage_b.images_failed,
            "evaluated_images": len(evaluated_ids),
            "coverage_fraction": (
                len(evaluated_ids) / inventory.image_count if inventory.image_count else 0.0
            ),
        }

        return {
            "stage_a": {},
            "stage_b": stage_b.to_dict(),
            "ap": ap.to_dict(),
            "operational": operational,
            "groups": groups,
            "uncertainty": uncertainty,
            "false_positive_deduplication": dedup,
            "coverage": coverage,
            "_ap_object": ap,
            "_operational_match": operational_match,
        }

    # -- gates -------------------------------------------------------------

    def _gates(
        self,
        inventory: DatasetInventory,
        leakage: LeakageReport,
        preflight: PreflightReport,
        stage_a: StageAResult,
        stage_b: StageBResult,
        metrics: Dict[str, Any],
        route_replay: Optional[RouteReplayReport],
        *,
        mutation_detected: bool,
        reference_session_ids: Optional[Iterable[str]],
        reference_image_paths: Optional[Iterable[Path]],
        min_class_samples: int,
    ) -> List[GateResult]:
        ap: APMetrics = metrics["_ap_object"]
        class_names = list(preflight.config.supported_classes.values())
        gates: List[GateResult] = []

        # 1. Dataset independence
        sessions_complete = (
            inventory.missing_session_count == 0 and len(inventory.sessions) > 0
        )
        has_provenance = bool(inventory.provenance)
        has_reference_check = bool(
            list(reference_session_ids or ()) or list(reference_image_paths or ())
        )
        if leakage.errors:
            status = EvaluationStatus.FAIL
            detail = "Leakage errors: " + "; ".join(issue.detail for issue in leakage.errors[:3])
        elif not sessions_complete:
            status = EvaluationStatus.NOT_ASSESSED
            detail = (
                "No complete session metadata; adjacent-frame/session independence "
                "cannot be verified."
            )
        elif not has_provenance:
            status = EvaluationStatus.NOT_ASSESSED
            detail = "No independent collection provenance recorded in the manifest."
        elif not has_reference_check:
            status = EvaluationStatus.CONDITIONAL
            detail = (
                "Internal session/duplicate checks passed, but no reference "
                "session list or reference imagery was supplied to prove separation "
                "from the training corpus."
            )
        elif leakage.warnings:
            status = EvaluationStatus.CONDITIONAL
            detail = (
                "No error-level leakage, but warnings remain: "
                + "; ".join(issue.detail for issue in leakage.warnings[:3])
            )
        else:
            status = EvaluationStatus.PASS
            detail = "Sessions, provenance, reference separation and duplicate checks passed."
        gates.append(
            GateResult(
                gate="dataset_independence",
                status=status,
                detail=detail,
                evidence=leakage.to_dict(),
            )
        )

        # 2. Annotation reliability
        annotation = inventory.annotation or {}
        qc = inventory.quality_control or {}
        manifest = inventory.manifest or {}
        policy = (
            annotation.get("policy")
            or annotation.get("guideline")
            or annotation.get("annotation_policy")
            or manifest.get("annotation_policy")
        )
        version = inventory.annotation_version()
        annotator_a = bool(qc.get("annotator_a") or qc.get("independent_annotator_a"))
        annotator_b = bool(qc.get("annotator_b") or qc.get("independent_annotator_b"))
        adjudication = bool(qc.get("adjudication") or qc.get("third_reviewer"))
        if version and policy and annotator_a and annotator_b and adjudication:
            status = EvaluationStatus.PASS
            detail = "Annotation policy, version, independent A/B review and adjudication recorded."
        elif version or policy or qc:
            status = EvaluationStatus.CONDITIONAL
            detail = (
                "Annotation documentation is incomplete: "
                f"version={bool(version)}, policy={bool(policy)}, "
                f"annotator_a={annotator_a}, annotator_b={annotator_b}, "
                f"adjudication={adjudication}."
            )
        else:
            status = EvaluationStatus.NOT_ASSESSED
            detail = "No annotation policy, version, or QC evidence recorded."
        gates.append(
            GateResult(
                gate="annotation_reliability",
                status=status,
                detail=detail,
                evidence={
                    "annotation_version": version,
                    "policy_recorded": bool(policy),
                    "annotator_a": annotator_a,
                    "annotator_b": annotator_b,
                    "adjudication": adjudication,
                    "quality_control": dict(qc),
                },
            )
        )

        # 3. Reproducibility
        checkpoint = preflight.checkpoint
        if mutation_detected:
            status = EvaluationStatus.FAIL
            detail = "Checkpoint or production configuration changed during evaluation."
        elif (
            not checkpoint.sha256
            or not preflight.config.detection_config_sha256
            or not preflight.config.severity_config_sha256
            or not inventory.dataset_sha256
        ):
            status = EvaluationStatus.NOT_ASSESSED
            detail = "Checkpoint, configuration, or dataset hash missing."
        else:
            status = EvaluationStatus.PASS
            detail = "Checkpoint, configuration, dataset manifest hash and environment recorded."
        gates.append(
            GateResult(
                gate="reproducibility",
                status=status,
                detail=detail,
                evidence={
                    "checkpoint_sha256": checkpoint.sha256,
                    "checkpoint_bytes": checkpoint.size_bytes,
                    "detection_config_sha256": preflight.config.detection_config_sha256,
                    "severity_config_sha256": preflight.config.severity_config_sha256,
                    "dataset_sha256": inventory.dataset_sha256,
                    "dataset_version": inventory.dataset_version(),
                    "annotation_version": inventory.annotation_version(),
                    "environment": dict(preflight.environment),
                    "mutation_detected": mutation_detected,
                },
            )
        )

        # 4. Metric completeness
        ground_truth_counts = {
            name: (ap.per_class[name].ground_truth_count if name in ap.per_class else 0)
            for name in class_names
        }
        insufficient = [
            name
            for name in class_names
            if insufficient_sample(ground_truth_counts[name], min_class_samples)
        ]
        if not stage_b.ran:
            status = EvaluationStatus.NOT_ASSESSED
            detail = "Stage B production inference was not run."
        elif ap.map50 is None:
            status = EvaluationStatus.NOT_ASSESSED
            detail = "No evaluable AP (no ground-truth hazards)."
        elif insufficient:
            status = EvaluationStatus.CONDITIONAL
            detail = (
                "Insufficient class samples for reliable reporting: "
                + ", ".join(f"{name}={ground_truth_counts[name]}" for name in insufficient)
                + f" (minimum {min_class_samples})."
            )
        elif stage_b.images_failed:
            status = EvaluationStatus.CONDITIONAL
            detail = f"{stage_b.images_failed} image(s) failed inference and were excluded."
        elif ap.classes_insufficient:
            status = EvaluationStatus.CONDITIONAL
            detail = f"Undefined AP for classes: {list(ap.classes_insufficient)}."
        else:
            status = EvaluationStatus.PASS
            detail = (
                "Overall and per-class AP, sample counts, operational metrics and "
                "session-clustered uncertainty reported."
            )
        gates.append(
            GateResult(
                gate="metric_completeness",
                status=status,
                detail=detail,
                evidence={
                    "map50": ap.map50,
                    "map50_95": ap.map50_95,
                    "per_class_ground_truth_counts": ground_truth_counts,
                    "insufficient_classes": insufficient,
                    "minimum_class_samples": min_class_samples,
                    "coverage": metrics["coverage"],
                },
            )
        )

        # 5. Production parity
        if not stage_b.ran:
            status = EvaluationStatus.NOT_ASSESSED
            detail = "Stage B production inference was not run; parity cannot be assessed."
        elif stage_b.invalid_detections:
            status = EvaluationStatus.FAIL
            detail = (
                f"{stage_b.invalid_detections} production detection(s) had invalid boxes or "
                "confidence values."
            )
        elif stage_b.below_threshold_detections:
            status = EvaluationStatus.FAIL
            detail = (
                f"{stage_b.below_threshold_detections} detection(s) fell below the configured "
                "0.25 threshold, indicating a confidence-contract violation."
            )
        elif stage_b.coordinate_mode != "bbox_norm_original_image":
            status = EvaluationStatus.FAIL
            detail = f"Unexpected coordinate mode: {stage_b.coordinate_mode}"
        elif stage_b.images_failed:
            status = EvaluationStatus.CONDITIONAL
            detail = f"{stage_b.images_failed} image(s) failed production inference."
        elif stage_a.ran and stage_a.per_class_ap50:
            differences: Dict[str, Optional[float]] = {}
            for name in class_names:
                stage_a_value = stage_a.per_class_ap50.get(name)
                stage_b_value = ap.per_class[name].ap50 if name in ap.per_class else None
                differences[name] = (
                    abs(stage_a_value - stage_b_value)
                    if stage_a_value is not None and stage_b_value is not None
                    else None
                )
            large = {
                name: value
                for name, value in differences.items()
                if value is not None and value > STAGE_A_AP_TOLERANCE
            }
            if large:
                status = EvaluationStatus.CONDITIONAL
                detail = (
                    "Stage A/B AP50 divergence exceeds tolerance; investigate "
                    f"coordination/rescaling: {large}"
                )
            else:
                status = EvaluationStatus.PASS
                detail = (
                    "Stage A and Stage B ran; class handling, coordinate rescaling and "
                    "unsupported-class exclusion verified. AP semantics caveat recorded."
                )
        else:
            status = EvaluationStatus.CONDITIONAL
            detail = (
                "Stage B structural parity verified, but Stage A did not produce "
                f"comparable AP: {stage_a.error or 'not run'}."
            )
        gates.append(
            GateResult(
                gate="production_parity",
                status=status,
                detail=detail,
                evidence={
                    "stage_a": stage_a.to_dict(),
                    "stage_b": stage_b.to_dict(),
                    "coordinate_mode": stage_b.coordinate_mode,
                    "threshold": preflight.config.conf,
                    "unsupported_classes": list(preflight.config.unsupported_classes),
                },
            )
        )

        # 6. Decision impact
        if route_replay is None:
            status = EvaluationStatus.NOT_ASSESSED
            detail = "Ground-truth route replay was not run."
        elif not route_replay.enough_evidence:
            status = EvaluationStatus.CONDITIONAL
            detail = (
                "Route replay ran but coverage is incomplete "
                f"({route_replay.images_replayed}/{route_replay.images_total} images)."
            )
        else:
            status = EvaluationStatus.PASS
            detail = (
                "Route replay completed offline; rank correlation, reversals and "
                "research-eligibility changes are reported. Production scoring is unchanged."
            )
        gates.append(
            GateResult(
                gate="decision_impact",
                status=status,
                detail=detail,
                evidence=route_replay.to_dict() if route_replay else {},
            )
        )

        # 7. Safety honesty
        gates.append(
            GateResult(
                gate="safety_honesty",
                status=EvaluationStatus.PASS,
                detail=(
                    "Report is evidence-scoped. No claim of safety, production accuracy, "
                    "or deployment readiness is made; a PASS would cover Phase 42 "
                    "requirements only."
                ),
                evidence={"harness_only": preflight.harness_only},
            )
        )
        return gates

    # -- orchestration -----------------------------------------------------

    def run(
        self,
        dataset_yaml: Path,
        *,
        manifest_path: Optional[Path] = None,
        split: str = "test",
        detector: Optional[Any] = None,
        stage_a_runner: Optional[Callable[..., Any]] = None,
        run_stage_a: bool = True,
        run_stage_b: bool = True,
        run_route_replay: bool = True,
        reference_session_ids: Optional[Iterable[str]] = None,
        reference_image_paths: Optional[Iterable[Path]] = None,
        min_class_samples: int = DEFAULT_MIN_SAMPLES,
        eligibility_min_score: float = 60.0,
        output_json: Optional[Path] = None,
    ) -> EvaluationReport:
        preflight = self.preflight()
        before = self._artifact_snapshot(preflight)

        inventory = collect_dataset(
            dataset_yaml,
            manifest_path=manifest_path,
            workspace_root=self.workspace_root,
            split=split,
            require_session_metadata=False,
        )
        if inventory.image_count == 0:
            raise EmptyDatasetError("Evaluation dataset is empty")

        leakage = analyze_leakage(
            inventory,
            reference_session_ids=reference_session_ids,
            reference_image_paths=reference_image_paths,
        )

        if run_stage_a:
            stage_a = self.run_stage_a(
                inventory.dataset_yaml, preflight, split=split, runner=stage_a_runner
            )
        else:
            stage_a = StageAResult(
                ran=False,
                metrics={},
                per_class_ap50={},
                caveat="Stage A was not requested.",
                error="not run",
                command={},
            )

        if run_stage_b:
            stage_b = self.run_stage_b(inventory, preflight, detector=detector)
            metrics = self._compute_metrics(
                inventory,
                stage_b,
                preflight.config,
                min_class_samples=min_class_samples,
            )
            metrics["stage_a"] = stage_a.to_dict()
        else:
            stage_b = StageBResult(
                ran=False,
                predictions_by_image={},
                images_inferred=0,
                images_failed=0,
                failed_image_ids=(),
                failed_reasons={},
                unsupported_detections_excluded=0,
                below_threshold_detections=0,
                invalid_detections=0,
                total_detections=0,
                coordinate_mode="not_run",
                inference_ms=0.0,
                caveat=("Stage B was not requested.",),
            )
            metrics = {
                "stage_a": stage_a.to_dict(),
                "stage_b": stage_b.to_dict(),
                "ap": {},
                "operational": {},
                "groups": {},
                "uncertainty": {},
                "false_positive_deduplication": {},
                "coverage": {
                    "images_total": inventory.image_count,
                    "coverage_fraction": 0.0,
                },
                "_ap_object": APMetrics({}, None, None, (), tuple(inventory.class_names.values())),
                "_operational_match": None,
            }

        replay: Optional[RouteReplayReport] = None
        replay_caveat: Optional[str] = None
        if run_route_replay and stage_b.ran:
            missing_route_metadata = [
                image.image_id
                for image in inventory.images
                if not image.route_id or not image.segment_id
            ]
            if missing_route_metadata:
                replay_caveat = (
                    f"Route replay skipped: {len(missing_route_metadata)} image(s) lack "
                    "route_id/segment_id metadata."
                )
            else:
                try:
                    replay = replay_routes(
                        inventory,
                        stage_b.predictions_by_image,
                        eligibility_min_score=eligibility_min_score,
                    )
                except RouteReplayError as exc:
                    replay_caveat = f"Route replay skipped: {exc}"

        after = self._artifact_snapshot(preflight)
        mutation_detected = before != after

        gates = self._gates(
            inventory,
            leakage,
            preflight,
            stage_a,
            stage_b,
            metrics,
            replay,
            mutation_detected=mutation_detected,
            reference_session_ids=reference_session_ids,
            reference_image_paths=reference_image_paths,
            min_class_samples=min_class_samples,
        )

        statuses = [gate.status for gate in gates]
        if preflight.harness_only:
            overall = (
                EvaluationStatus.FAIL
                if EvaluationStatus.FAIL in statuses
                else EvaluationStatus.NOT_ASSESSED
            )
        elif EvaluationStatus.FAIL in statuses:
            overall = EvaluationStatus.FAIL
        elif EvaluationStatus.NOT_ASSESSED in statuses:
            overall = EvaluationStatus.NOT_ASSESSED
        elif EvaluationStatus.CONDITIONAL in statuses:
            overall = EvaluationStatus.CONDITIONAL
        else:
            overall = EvaluationStatus.PASS

        caveats = list(preflight.warnings)
        caveats.extend(stage_b.caveat)
        caveats.append(stage_a.caveat)
        if replay_caveat:
            caveats.append(replay_caveat)
        if mutation_detected:
            caveats.append("Artifact mutation detected during evaluation; gates marked FAIL.")
        if preflight.harness_only:
            caveats.append(
                "HARNESS-ONLY run: metrics do not describe the genuine "
                "saferoute-yolo11-v2 serving checkpoint."
            )

        safety_note = (
            "Phase 42 evaluates detector evidence reliability. It does not certify "
            "SafeRoute AI as safe for public deployment, and its result applies only "
            "to the exact checkpoint, configuration and dataset hashes recorded here."
        )

        metrics["stage_a"] = stage_a.to_dict()
        report = EvaluationReport(
            status=overall,
            harness_only=preflight.harness_only,
            gates=tuple(gates),
            preflight=preflight,
            dataset=summarise_inventory(inventory),
            leakage=leakage.to_dict(),
            stage_a=stage_a.to_dict(),
            stage_b=stage_b.to_dict(),
            metrics={
                key: value
                for key, value in metrics.items()
                if not key.startswith("_")
            },
            route_replay=replay.to_dict() if replay else None,
            caveats=tuple(caveats),
            safety_note=safety_note,
            generated_utc=datetime.now(timezone.utc).isoformat(),
            artifacts={
                "before": before,
                "after": after,
                "mutation_detected": mutation_detected,
                "production_scoring_modified": False,
                "serving_checkpoint_modified": mutation_detected,
            },
        )
        if output_json:
            report.write_json(Path(output_json))
        return report


__all__ = [
    "CheckpointIdentity",
    "EvaluationError",
    "EvaluationReport",
    "EvaluationStatus",
    "GateResult",
    "IndependentEvaluator",
    "InferenceConfig",
    "ModelIntegrityError",
    "PreflightReport",
    "ProductionParityError",
    "SmokeSubstituteError",
    "StageAResult",
    "StageBResult",
    "identify_checkpoint",
    "load_production_config",
]
