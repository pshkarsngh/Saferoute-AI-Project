"""SafeRoute AI — OpenCV Preprocessing & Image-Quality Pipeline.

Version: preprocess-v1
Implements single, versioned, deterministic OpenCV validation, letterbox resizing,
inference preparation, and non-destructive visualisation.
Governing rules: master_rules.md Rule 6, TRD §7, ARCHITECTURE §6.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import os
import yaml
import numpy as np
import cv2

__version__ = "preprocess-v1"


class ImageStatusCode(str, Enum):
    """Categorical classification of image validation outcomes."""
    OK = "ok"
    EMPTY = "empty"
    UNREADABLE = "unreadable"
    CORRUPT = "corrupt"
    UNSUPPORTED = "unsupported"
    TOO_SMALL = "too_small"
    LOW_QUALITY = "low_quality"


@dataclass(frozen=True)
class ImageStatus:
    """Structured result returned by image validation."""
    code: ImageStatusCode
    is_valid: bool
    path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    channels: Optional[int] = None
    file_size_bytes: int = 0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value,
            "is_valid": self.is_valid,
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "channels": self.channels,
            "file_size_bytes": self.file_size_bytes,
            "message": self.message,
        }


@dataclass
class PreparedImage:
    """Standardized representation of a preprocessed image."""
    image: np.ndarray             # Preprocessed BGR image (letterboxed)
    original_shape: Tuple[int, int, int]  # (height, width, channels)
    target_shape: Tuple[int, int]         # (height, width)
    ratio: Tuple[float, float]            # (ratio_w, ratio_h)
    pad: Tuple[int, int]                  # (pad_w, pad_h) in pixels
    pipeline_version: str = __version__


@dataclass
class DetectionBox:
    """Representation of an object detection bounding box for visualisation."""
    class_name: str
    confidence: float
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2) in pixels


def load_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load configuration from a YAML file or default workspace path."""
    if config_path is None:
        workspace_root = Path(__file__).resolve().parent.parent.parent
        config_path = workspace_root / "config" / "preprocessing.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.is_file():
        raise FileNotFoundError(f"Preprocessing config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


class PreprocessingPipeline:
    """Single versioned OpenCV validation and preprocessing pipeline."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[Union[str, Path]] = None):
        if config is not None:
            self.config = config
        else:
            self.config = load_config(config_path)

        self.version = self.config.get("pipeline_version", __version__)
        
        # Validation parameters
        v_cfg = self.config.get("validation", {})
        self.min_width = int(v_cfg.get("min_width", 32))
        self.min_height = int(v_cfg.get("min_height", 32))
        self.min_channels = int(v_cfg.get("min_channels", 3))
        self.max_channels = int(v_cfg.get("max_channels", 3))
        self.supported_exts = tuple(ext.lower() for ext in v_cfg.get("supported_extensions", [".jpg", ".jpeg", ".png", ".bmp", ".webp"]))

        # Preprocessing parameters
        p_cfg = self.config.get("preprocessing", {})
        self.target_size = tuple(p_cfg.get("target_size", [640, 640]))
        self.auto = bool(p_cfg.get("auto", False))
        self.scale_fill = bool(p_cfg.get("scale_fill", False))
        self.scale_up = bool(p_cfg.get("scale_up", True))
        self.stride = int(p_cfg.get("stride", 32))
        self.pad_color = tuple(p_cfg.get("pad_color", [114, 114, 114]))

        # Enhancements
        e_cfg = self.config.get("enhancements", {})
        self.enable_clahe = bool(e_cfg.get("enable_clahe", False))
        self.clahe_clip_limit = float(e_cfg.get("clahe_clip_limit", 2.0))
        self.clahe_grid = tuple(e_cfg.get("clahe_tile_grid_size", [8, 8]))

        # Visualisation settings
        vis_cfg = self.config.get("visualisation", {})
        self.bbox_thickness = int(vis_cfg.get("bbox_thickness", 2))
        self.font_scale = float(vis_cfg.get("font_scale", 0.5))
        self.text_thickness = int(vis_cfg.get("text_thickness", 1))
        self.colors = vis_cfg.get("colors", {})

    def validate_image(self, path_or_bytes: Union[str, Path, bytes]) -> ImageStatus:
        """Validate image existence, readability, dimensions, and decodability.
        
        Never raises exceptions; always returns an explicit ImageStatus.
        """
        path_str: Optional[str] = None
        data_bytes: bytes

        if isinstance(path_or_bytes, (str, Path)):
            path_obj = Path(path_or_bytes)
            path_str = str(path_obj)

            if not path_obj.exists():
                return ImageStatus(
                    code=ImageStatusCode.UNREADABLE,
                    is_valid=False,
                    path=path_str,
                    message="File does not exist."
                )

            # Extension check
            ext = path_obj.suffix.lower()
            if ext not in self.supported_exts:
                return ImageStatus(
                    code=ImageStatusCode.UNSUPPORTED,
                    is_valid=False,
                    path=path_str,
                    message=f"Unsupported image extension '{ext}'. Expected one of {self.supported_exts}."
                )

            try:
                file_size = path_obj.stat().st_size
                if file_size == 0:
                    return ImageStatus(
                        code=ImageStatusCode.EMPTY,
                        is_valid=False,
                        path=path_str,
                        file_size_bytes=0,
                        message="File is zero bytes (empty)."
                    )
                with open(path_obj, "rb") as f:
                    data_bytes = f.read()
            except Exception as e:
                return ImageStatus(
                    code=ImageStatusCode.UNREADABLE,
                    is_valid=False,
                    path=path_str,
                    message=f"Error reading file: {e}"
                )
        elif isinstance(path_or_bytes, bytes):
            data_bytes = path_or_bytes
            file_size = len(data_bytes)
            if file_size == 0:
                return ImageStatus(
                    code=ImageStatusCode.EMPTY,
                    is_valid=False,
                    file_size_bytes=0,
                    message="Byte buffer is empty (0 bytes)."
                )
        else:
            return ImageStatus(
                code=ImageStatusCode.UNSUPPORTED,
                is_valid=False,
                message=f"Unsupported input type {type(path_or_bytes)}."
            )

        # Attempt OpenCV decode
        try:
            nparr = np.frombuffer(data_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            return ImageStatus(
                code=ImageStatusCode.CORRUPT,
                is_valid=False,
                path=path_str,
                file_size_bytes=file_size,
                message=f"OpenCV decode exception: {e}"
            )

        if img is None or img.size == 0:
            return ImageStatus(
                code=ImageStatusCode.CORRUPT,
                is_valid=False,
                path=path_str,
                file_size_bytes=file_size,
                message="OpenCV failed to decode image buffer (corrupted or invalid image data)."
            )

        h, w = img.shape[:2]
        c = img.shape[2] if len(img.shape) == 3 else 1

        if w < self.min_width or h < self.min_height:
            return ImageStatus(
                code=ImageStatusCode.TOO_SMALL,
                is_valid=False,
                path=path_str,
                width=w,
                height=h,
                channels=c,
                file_size_bytes=file_size,
                message=f"Image dimension ({w}x{h}) smaller than minimum allowed threshold ({self.min_width}x{self.min_height})."
            )

        if c < self.min_channels or c > self.max_channels:
            return ImageStatus(
                code=ImageStatusCode.UNSUPPORTED,
                is_valid=False,
                path=path_str,
                width=w,
                height=h,
                channels=c,
                file_size_bytes=file_size,
                message=f"Image channels ({c}) outside expected range ({self.min_channels}-{self.max_channels})."
            )

        return ImageStatus(
            code=ImageStatusCode.OK,
            is_valid=True,
            path=path_str,
            width=w,
            height=h,
            channels=c,
            file_size_bytes=file_size,
            message="Image successfully verified and decoded."
        )

    def letterbox(
        self,
        im: np.ndarray,
        new_shape: Optional[Tuple[int, int]] = None,
        color: Optional[Tuple[int, int, int]] = None,
        auto: Optional[bool] = None,
        scale_fill: Optional[bool] = None,
        scale_up: Optional[bool] = None,
        stride: Optional[int] = None,
    ) -> Tuple[np.ndarray, Tuple[float, float], Tuple[int, int]]:
        """Resize and pad image while preserving aspect ratio (Ultralytics-compatible).
        
        Returns:
            (resized_and_padded_image, (ratio_w, ratio_h), (pad_w, pad_h))
        """
        new_shape = new_shape if new_shape is not None else self.target_size
        color = color if color is not None else self.pad_color
        auto = auto if auto is not None else self.auto
        scale_fill = scale_fill if scale_fill is not None else self.scale_fill
        scale_up = scale_up if scale_up is not None else self.scale_up
        stride = stride if stride is not None else self.stride

        shape = im.shape[:2]  # current shape [height, width]
        if isinstance(new_shape, int):
            new_shape = (new_shape, new_shape)

        # Scale ratio (new / old)
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        if not scale_up:  # only scale down, do not scale up
            r = min(r, 1.0)

        # Compute padding
        ratio = (r, r)
        new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding

        if auto:  # minimum rectangle
            dw, dh = np.mod(dw, stride), np.mod(dh, stride)
        elif scale_fill:  # stretch
            dw, dh = 0, 0
            new_unpad = (new_shape[1], new_shape[0])
            ratio = (new_shape[1] / shape[1], new_shape[0] / shape[0])

        dw /= 2  # divide padding into 2 sides
        dh /= 2

        if shape[::-1] != new_unpad:  # resize
            im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)

        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        return im, ratio, (left, top)

    def preprocess(self, image: np.ndarray) -> PreparedImage:
        """Apply deterministic, documented preprocessing transforms.
        
        Transforms:
        1. Non-destructive copy of input image.
        2. Letterbox resize to preserve aspect ratio.
        3. Optional CLAHE (disabled by default; applied only if configured).
        """
        if not isinstance(image, np.ndarray) or image.size == 0:
            raise ValueError("Input image must be a non-empty numpy.ndarray.")

        orig_shape = image.shape
        # Ensure working on a separate copy
        processed = image.copy()

        if self.enable_clahe:
            # Apply CLAHE to L-channel in Lab color space to preserve color balance
            lab = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=self.clahe_clip_limit, tileGridSize=self.clahe_grid)
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            processed = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

        letterboxed, ratio, pad = self.letterbox(processed)
        target_shape = (letterboxed.shape[0], letterboxed.shape[1])

        return PreparedImage(
            image=letterboxed,
            original_shape=orig_shape,
            target_shape=target_shape,
            ratio=ratio,
            pad=pad,
            pipeline_version=self.version
        )

    def prepare_inference_input(self, image: np.ndarray) -> Tuple[np.ndarray, PreparedImage]:
        """Prepare image array for YOLO11 neural network inference.
        
        Converts BGR letterboxed image to normalized RGB CHW tensor format:
        - BGR -> RGB
        - HWC -> CHW
        - [0, 255] uint8 -> [0.0, 1.0] float32
        """
        prepared = self.preprocess(image)
        im = prepared.image

        # BGR to RGB
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        # HWC to CHW
        im = im.transpose((2, 0, 1))
        # Ensure contiguous array
        im = np.ascontiguousarray(im, dtype=np.float32)
        # Scale 0 - 255 to 0.0 - 1.0
        im /= 255.0

        return im, prepared

    def visualise(
        self,
        image: np.ndarray,
        detections: List[DetectionBox],
        output_path: Optional[Union[str, Path]] = None
    ) -> np.ndarray:
        """Draw detections onto a fresh copy of the image and optionally save to an artifact path.
        
        Never modifies the original input image array or source image file.
        """
        if not isinstance(image, np.ndarray):
            raise ValueError("Input image must be a numpy.ndarray.")

        canvas = image.copy()

        for det in detections:
            x1, y1, x2, y2 = [int(round(v)) for v in det.bbox]
            cls_name = det.class_name.lower()
            color = tuple(self.colors.get(cls_name, self.colors.get("default", [0, 255, 0])))

            # Draw bounding box
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, self.bbox_thickness)

            # Label text
            label = f"{det.class_name} {det.confidence:.2f}"
            (text_w, text_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, self.text_thickness
            )
            
            # Label background box
            bg_y1 = max(0, y1 - text_h - baseline - 4)
            bg_y2 = y1
            cv2.rectangle(canvas, (x1, bg_y1), (x1 + text_w + 4, bg_y2), color, -1)

            # Label text in white/black
            text_color = (255, 255, 255)
            cv2.putText(
                canvas,
                label,
                (x1 + 2, y1 - baseline - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.font_scale,
                text_color,
                self.text_thickness,
                lineType=cv2.LINE_AA
            )

        if output_path is not None:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(out_file), canvas)

        return canvas


# Default module-level singleton instance
_default_pipeline: Optional[PreprocessingPipeline] = None


def get_pipeline() -> PreprocessingPipeline:
    """Retrieve or initialize the default singleton PreprocessingPipeline."""
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = PreprocessingPipeline()
    return _default_pipeline


def validate_image(path_or_bytes: Union[str, Path, bytes]) -> ImageStatus:
    """Functional wrapper for validate_image."""
    return get_pipeline().validate_image(path_or_bytes)


def preprocess(image: np.ndarray) -> PreparedImage:
    """Functional wrapper for preprocess."""
    return get_pipeline().preprocess(image)


def prepare_inference_input(image: np.ndarray) -> Tuple[np.ndarray, PreparedImage]:
    """Functional wrapper for prepare_inference_input."""
    return get_pipeline().prepare_inference_input(image)


def visualise(
    image: np.ndarray,
    detections: List[DetectionBox],
    output_path: Optional[Union[str, Path]] = None
) -> np.ndarray:
    """Functional wrapper for visualise."""
    return get_pipeline().visualise(image, detections, output_path)
