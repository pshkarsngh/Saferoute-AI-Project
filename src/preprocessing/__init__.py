"""SafeRoute AI — Preprocessing Package.

Exposes single versioned preprocessing pipeline and public contract functions.
"""

from src.preprocessing.pipeline import (
    __version__,
    ImageStatusCode,
    ImageStatus,
    PreparedImage,
    DetectionBox,
    PreprocessingPipeline,
    get_pipeline,
    validate_image,
    preprocess,
    prepare_inference_input,
    visualise,
)

__all__ = [
    "__version__",
    "ImageStatusCode",
    "ImageStatus",
    "PreparedImage",
    "DetectionBox",
    "PreprocessingPipeline",
    "get_pipeline",
    "validate_image",
    "preprocess",
    "prepare_inference_input",
    "visualise",
]
