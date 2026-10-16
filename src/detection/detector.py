"""SafeRoute AI — Versioned Hazard Detection Module.

Module Version: detect-v1
Model Version: resolved per loaded checkpoint (default serving: saferoute-yolo11-v2)
Governing rules: master_rules.md Rules 1, 4, 5, 6, 7, 9, 12, 14, 16, 18, 20.
TRD §7, ARCHITECTURE §4, §5.7, §6.
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
import yaml

from src.preprocessing.pipeline import (
    ImageStatus,
    ImageStatusCode,
    PreprocessingPipeline,
    __version__ as PREPROCESS_VERSION,
)
from src.detection.schemas import (
    DetectionRecord,
    DetectionStatus,
    ImageDetectionResult,
)

__version__ = "detect-v2"
MODEL_VERSION = "saferoute-yolo11-v2"

# Supported target classes verified from PHASE_03 audit and PHASE_07/08
SUPPORTED_CLASSES = {
    0: "pothole",
    1: "crack",
}

DEFAULT_CHECKPOINT_REL = Path("models/training/saferoute-yolo11-v2/weights/best.pt")
DEFAULT_DETECTION_CONFIG = Path("config/detection.yaml")


class HazardDetector:
    """Production inference detector for road hazards.
    
    Loads the accepted YOLO11 baseline checkpoint, invokes the versioned
    OpenCV preprocessing pipeline from PHASE_06, and emits structured detection records.
    
    Hard constraints:
    - Never computes route safety scores (Rule 7, Rule 12).
    - Fails explicitly on missing checkpoints or corrupt images (Rule 14).
    - Never mutates or overwrites source images (Rule 1).
    - Discloses unsupported classes honestly (Rule 5).
    """

    def __init__(
        self,
        checkpoint_path: Optional[Union[str, Path]] = None,
        conf_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        device: Optional[Union[int, str]] = None,
        workspace_root: Optional[Union[str, Path]] = None,
        preprocessing_pipeline: Optional[PreprocessingPipeline] = None,
        config_path: Optional[Union[str, Path]] = None,
        config_dict: Optional[Dict[str, Any]] = None,
    ):
        self.detector_version = __version__

        if workspace_root is None:
            self.workspace_root = Path(__file__).resolve().parent.parent.parent
        else:
            self.workspace_root = Path(workspace_root).resolve()

        # Load inference configuration; explicit arguments override config values.
        cfg = config_dict
        if cfg is None:
            cfg_p = Path(config_path) if config_path else (self.workspace_root / DEFAULT_DETECTION_CONFIG)
            cfg = {}
            if cfg_p.is_file():
                with open(cfg_p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
        inf = cfg.get("inference", {})
        self.imgsz = int(inf.get("imgsz", 640))
        self.conf_threshold = float(conf_threshold if conf_threshold is not None else inf.get("conf", 0.25))
        self.iou_threshold = float(iou_threshold if iou_threshold is not None else inf.get("iou", 0.45))
        self.max_det = int(inf.get("max_det", 300))
        self.augment = bool(inf.get("augment", False))
        self.batch = int(inf.get("batch", 1))

        if checkpoint_path is None:
            # PHASE_24G: the serving checkpoint is taken from the detection
            # configuration (config/detection.yaml -> model.checkpoint) so the
            # promoted checkpoint is actually what gets loaded. The module
            # constant below is only a fallback when that key/config is absent.
            configured_ckpt = (cfg.get("model") or {}).get("checkpoint")
            if configured_ckpt:
                self.checkpoint_path = (self.workspace_root / Path(str(configured_ckpt))).resolve()
            else:
                self.checkpoint_path = (self.workspace_root / DEFAULT_CHECKPOINT_REL).resolve()
        else:
            self.checkpoint_path = Path(checkpoint_path).resolve()

        # model_version identifies the checkpoint that was ACTUALLY loaded
        # (src/detection/schemas.py: "Checkpoint model identifier"), not merely
        # the configured serving release. This keeps explicitly-supplied
        # checkpoints (e.g. the v1 model) correctly labelled.
        self.model_version = self._resolve_model_version()

        # Workspace isolation verification (Rule 1)
        self._verify_workspace_path(self.checkpoint_path, "Checkpoint path")

        # Initialize shared preprocessing pipeline (Rule 6)
        if preprocessing_pipeline is not None:
            self.pipeline = preprocessing_pipeline
        else:
            self.pipeline = PreprocessingPipeline()

        # Device selection (Rule 16)
        if device is None:
            import torch
            self.device = 0 if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Load YOLO model
        self.model = None
        self._load_model()

    def _verify_workspace_path(self, path: Path, label: str):
        """Ensure path resolves strictly inside workspace (Rule 1)."""
        try:
            path.relative_to(self.workspace_root)
        except ValueError:
            raise RuntimeError(f"Rule 1 violation: {label} '{path}' is outside workspace '{self.workspace_root}'.")

    def _resolve_model_version(self) -> str:
        """Return the model identifier of the checkpoint actually loaded.

        ``model_version`` is the "checkpoint model identifier" that produced the
        detections (``src/detection/schemas.py``), i.e. the loaded weights, not a
        fixed serving label. The project stores each trained model at
        ``models/training/<identifier>/weights/<file>.pt`` (TRD §5.6,
        ARCHITECTURE §5.6), so the canonical identifier is the model directory
        name. Custom paths that do not follow that layout fall back to the
        default serving identifier (``MODEL_VERSION``).
        """
        parts = self.checkpoint_path.parts
        if len(parts) >= 3 and parts[-2] == "weights":
            candidate = parts[-3]
            if candidate.startswith("saferoute-yolo11-"):
                return candidate
        return MODEL_VERSION

    def _load_model(self):
        """Explicitly load the approved checkpoint weights."""
        if not self.checkpoint_path.is_file():
            # ARCHITECTURE §5.7: Never fall back silently to another model or random weights
            raise FileNotFoundError(
                f"Approved model checkpoint not found at '{self.checkpoint_path}'. "
                f"Silent fallback to unapproved models is strictly forbidden."
            )

        try:
            from ultralytics import YOLO
            self.model = YOLO(str(self.checkpoint_path))
        except Exception as e:
            raise RuntimeError(f"Failed to load checkpoint '{self.checkpoint_path}': {e}") from e

    def detect(
        self,
        image_input: Union[str, Path, np.ndarray, bytes],
        image_id: Optional[str] = None,
        route_id: Optional[str] = None,
        segment_id: Optional[str] = None,
        conf: Optional[float] = None,
    ) -> ImageDetectionResult:
        """Run end-to-end inference on a single image input.
        
        Args:
            image_input: File path, raw bytes, or loaded BGR numpy ndarray.
            image_id: Optional identifier for tracing.
            route_id: Optional route identifier.
            segment_id: Optional route segment identifier.
            conf: Optional confidence threshold override.
            
        Returns:
            ImageDetectionResult with complete structured metadata and detections.
        """
        timing = {}
        t_start = time.perf_counter()
        active_conf = conf if conf is not None else self.conf_threshold

        # Determine image_id if path was provided
        if image_id is None and isinstance(image_input, (str, Path)):
            image_id = Path(image_input).name

        # 1. Validation check via PHASE_06 pipeline
        t0 = time.perf_counter()
        if isinstance(image_input, np.ndarray):
            success, encoded = cv2.imencode(".jpg", image_input)
            if not success:
                return ImageDetectionResult(
                    model_version=self.model_version,
                    pipeline_version=self.pipeline.version,
                    status=DetectionStatus.INVALID_IMAGE,
                    image_id=image_id,
                    route_id=route_id,
                    segment_id=segment_id,
                    error="Failed to encode numpy.ndarray to image format for validation.",
                    timing_ms={"total": (time.perf_counter() - t_start) * 1000.0},
                )
            validation_input = encoded.tobytes()
        else:
            validation_input = image_input

        validation_status = self.pipeline.validate_image(validation_input)
        timing["validate"] = (time.perf_counter() - t0) * 1000.0

        if not validation_status.is_valid:
            # Explicit failure on invalid image; excluded from hazard evidence (Rule 9)
            return ImageDetectionResult(
                model_version=self.model_version,
                pipeline_version=self.pipeline.version,
                status=DetectionStatus.INVALID_IMAGE,
                image_id=image_id,
                route_id=route_id,
                segment_id=segment_id,
                error=f"Image validation failed [{validation_status.code.value}]: {validation_status.message}",
                timing_ms={"validate": timing["validate"], "total": (time.perf_counter() - t_start) * 1000.0},
            )

        # 2. Decode / obtain original image array (non-destructive)
        if isinstance(image_input, np.ndarray):
            original_bgr = image_input.copy()
        elif isinstance(image_input, (str, Path)):
            original_bgr = cv2.imread(str(image_input))
        elif isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            original_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            return ImageDetectionResult(
                model_version=self.model_version,
                pipeline_version=self.pipeline.version,
                status=DetectionStatus.INVALID_IMAGE,
                image_id=image_id,
                route_id=route_id,
                segment_id=segment_id,
                error=f"Unsupported image_input type: {type(image_input)}",
            )

        if original_bgr is None:
            return ImageDetectionResult(
                model_version=self.model_version,
                pipeline_version=self.pipeline.version,
                status=DetectionStatus.INVALID_IMAGE,
                image_id=image_id,
                route_id=route_id,
                segment_id=segment_id,
                error="Failed to decode image array into valid BGR pixels.",
            )

        # Robustness: accept single-channel (grayscale) and 4-channel (BGRA) inputs.
        if original_bgr.ndim == 2:
            original_bgr = cv2.cvtColor(original_bgr, cv2.COLOR_GRAY2BGR)
        elif original_bgr.ndim == 3 and original_bgr.shape[2] == 4:
            original_bgr = cv2.cvtColor(original_bgr, cv2.COLOR_BGRA2BGR)

        orig_h, orig_w = original_bgr.shape[:2]

        # 3. Preprocessing using PHASE_06 letterbox & transforms
        t0 = time.perf_counter()
        prepared = self.pipeline.preprocess(original_bgr)
        timing["preprocess"] = (time.perf_counter() - t0) * 1000.0

        # 4. Neural Network Inference
        t0 = time.perf_counter()
        try:
            # Predict using YOLO with preprocessed letterboxed image
            preds = self.model.predict(
                source=prepared.image,
                conf=active_conf,
                iou=self.iou_threshold,
                imgsz=self.imgsz,
                max_det=self.max_det,
                augment=self.augment,
                device=self.device,
                verbose=False,
            )
        except Exception as e:
            return ImageDetectionResult(
                model_version=self.model_version,
                pipeline_version=self.pipeline.version,
                status=DetectionStatus.FAILED,
                image_id=image_id,
                route_id=route_id,
                segment_id=segment_id,
                image_width=orig_w,
                image_height=orig_h,
                error=f"Inference execution failed: {type(e).__name__}: {e}",
                timing_ms={"preprocess": timing["preprocess"], "total": (time.perf_counter() - t_start) * 1000.0},
            )
        timing["inference"] = (time.perf_counter() - t0) * 1000.0

        # 5. Parse and map detections
        t0 = time.perf_counter()
        detections: List[DetectionRecord] = []
        pred_result = preds[0]

        pad_left, pad_top = prepared.pad
        scale_w, scale_h = prepared.ratio

        if len(pred_result.boxes) > 0:
            boxes_data = pred_result.boxes.data.cpu().numpy()
            # Each row: [x1, y1, x2, y2, conf, cls_id]
            for row in boxes_data:
                bx1, by1, bx2, by2, bconf, bcls = row[:6]
                cls_id = int(bcls)

                # Rescale coordinates back to original unpadded image space
                orig_x1 = max(0.0, (bx1 - pad_left) / scale_w)
                orig_y1 = max(0.0, (by1 - pad_top) / scale_h)
                orig_x2 = min(float(orig_w), (bx2 - pad_left) / scale_w)
                orig_y2 = min(float(orig_h), (by2 - pad_top) / scale_h)

                # Normalized coordinates within [0.0, 1.0]
                norm_x1 = max(0.0, min(1.0, orig_x1 / orig_w))
                norm_y1 = max(0.0, min(1.0, orig_y1 / orig_h))
                norm_x2 = max(0.0, min(1.0, orig_x2 / orig_w))
                norm_y2 = max(0.0, min(1.0, orig_y2 / orig_h))

                # Map to verified class names or disclose as unsupported (Rule 5)
                if cls_id in SUPPORTED_CLASSES:
                    class_name = SUPPORTED_CLASSES[cls_id]
                    rec_status = "detected"
                    err = None
                else:
                    class_name = f"unsupported_class_{cls_id}"
                    rec_status = "unsupported_class"
                    err = f"Class ID {cls_id} is unsupported in {self.model_version}."

                record = DetectionRecord(
                    model_version=self.model_version,
                    image_id=image_id,
                    route_id=route_id,
                    segment_id=segment_id,
                    hazard_class=class_name,
                    confidence=float(bconf),
                    bbox_xyxy=[orig_x1, orig_y1, orig_x2, orig_y2],
                    bbox_norm=[norm_x1, norm_y1, norm_x2, norm_y2],
                    status=rec_status,
                    error=err,
                )
                detections.append(record)

        timing["postprocess"] = (time.perf_counter() - t0) * 1000.0
        timing["total"] = (time.perf_counter() - t_start) * 1000.0

        # Distinct status for empty detections vs success (Rule 9)
        final_status = DetectionStatus.SUCCESS if detections else DetectionStatus.NO_DETECTIONS

        return ImageDetectionResult(
            model_version=self.model_version,
            pipeline_version=self.pipeline.version,
            status=final_status,
            image_id=image_id,
            route_id=route_id,
            segment_id=segment_id,
            detections=detections,
            image_width=orig_w,
            image_height=orig_h,
            error=None,
            timing_ms=timing,
        )

    def visualise(
        self,
        image_input: Union[str, Path, np.ndarray],
        result: ImageDetectionResult,
        output_path: Union[str, Path],
    ) -> Path:
        """Render detection boxes onto a COPY of the image and save to output_path.
        
        Hard constraint: NEVER overwrite the source image (Rule 1, Rule 18).
        """
        out_p = Path(output_path).resolve()
        self._verify_workspace_path(out_p, "Visualisation output path")

        # Load image copy
        if isinstance(image_input, (str, Path)):
            src_p = Path(image_input).resolve()
            if src_p == out_p:
                raise ValueError("Rule 1 violation: Cannot overwrite the source image with visualisation.")
            canvas = cv2.imread(str(src_p))
        elif isinstance(image_input, np.ndarray):
            canvas = image_input.copy()
        else:
            raise TypeError("Unsupported image type for visualisation.")

        if canvas is None:
            raise ValueError("Failed to load image canvas for visualisation.")

        # Draw detections
        for det in result.detections:
            x1, y1, x2, y2 = [int(round(c)) for c in det.bbox_xyxy]
            color = (0, 0, 255) if det.hazard_class == "pothole" else (0, 165, 255)  # Red for pothole, Orange for crack
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

            label = f"{det.hazard_class} {det.confidence:.2f}"
            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(canvas, (x1, max(0, y1 - th - baseline - 4)), (x1 + tw + 4, y1), color, -1)
            cv2.putText(canvas, label, (x1 + 2, y1 - baseline - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        out_p.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_p), canvas)
        return out_p

    def detect_batch(self, image_inputs: List[Union[str, Path, np.ndarray, bytes]], **kwargs) -> List[ImageDetectionResult]:
        """Run detection over many inputs, returning one structured result each.

        Iterates the hardened single-image path so every input kind (path, bytes,
        ndarray) and every failure mode is handled identically. Order is preserved.
        """
        return [self.detect(img, **kwargs) for img in image_inputs]
