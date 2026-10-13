# SafeRoute AI — Detection Pipeline (`src.detection`)

> **Module Version:** `detect-v1`  
> **Model Identifier:** `saferoute-yolo11-v1`  
> **Phase ID:** PHASE_10  
> **Governing rules:** [`../../master_rules.md`](../../master_rules.md) (Rules 1, 5, 6, 7, 9, 12, 14, 16, 20), TRD §7, ARCHITECTURE §4, §5.7, §6.

---

## 1. Overview

The `src.detection` package implements the production hazard detection pipeline for SafeRoute AI. It loads the approved YOLO11n checkpoint (`models/training/saferoute-yolo11-v1/weights/best.pt`), utilizes the versioned OpenCV preprocessing pipeline (`src.preprocessing.pipeline`, `preprocess-v1`), and emits structured detection records.

### Core Invariants:
1. **Never computes safety scores:** Detection produces raw bounding boxes and classification probabilities only. Safety scoring is exclusively owned by the deterministic risk engine in Phase 12 (Rule 7, Rule 12).
2. **Explicit failure paths:** Missing checkpoints, corrupt images, and inference faults return explicit error states; silent fallbacks are strictly prohibited (ARCHITECTURE §5.7).
3. **Missing evidence is not safety:** An empty detection outcome (`no_detections`) means the model found no hazards above threshold; it is never treated as proof of a safe road (Rule 9).
4. **Non-destructive:** Source images are never overwritten or altered (Rule 1, Rule 18).

---

## 2. API Contract

### `DetectionRecord` Schema
| Field | Type | Description |
|---|---|---|
| `model_version` | `str` | Approved model identifier (`saferoute-yolo11-v1`) |
| `image_id` | `Optional[str]` | Unique image identifier |
| `route_id` | `Optional[str]` | Associated route ID (for multi-route comparison) |
| `segment_id` | `Optional[str]` | Route segment ID |
| `hazard_class` | `str` | Detected class: `'pothole'`, `'crack'`, or `'unsupported_class'` |
| `confidence` | `float` | Detection confidence [0.0, 1.0] |
| `bbox_xyxy` | `List[float]` | Unnormalized pixel box `[x1, y1, x2, y2]` in original image |
| `bbox_norm` | `List[float]` | Normalized box `[nx1, ny1, nx2, ny2]` within `[0.0, 1.0]` |
| `status` | `str` | Record status (`'detected'`, `'unsupported_class'`) |
| `error` | `Optional[str]` | Error message if anomalous |

### `ImageDetectionResult` Schema
| Field | Type | Description |
|---|---|---|
| `model_version` | `str` | Model identifier |
| `pipeline_version` | `str` | Preprocessing pipeline version (`preprocess-v1`) |
| `status` | `DetectionStatus` | Outcome: `SUCCESS`, `NO_DETECTIONS`, `INVALID_IMAGE`, `MISSING_CHECKPOINT`, `FAILED` |
| `image_id` | `Optional[str]` | Image identifier |
| `route_id` | `Optional[str]` | Route identifier |
| `segment_id` | `Optional[str]` | Segment identifier |
| `image_width` | `Optional[int]` | Original image width |
| `image_height` | `Optional[int]` | Original image height |
| `detections_count` | `int` | Number of detected hazard objects |
| `detections` | `List[DetectionRecord]` | List of individual hazard detections |
| `error` | `Optional[str]` | Error details if status is not success/no_detections |
| `timing_ms` | `Dict[str, float]` | Execution breakdown (`validate`, `preprocess`, `inference`, `postprocess`, `total`) |

---

## 3. Supported Classes & Honest Disclosure (Rule 5)

| Class ID | Name | Detector Status | Notes |
|---|---|---|---|
| `0` | `pothole` | **SUPPORTED** | Trained & validated |
| `1` | `crack` | **SUPPORTED** | Trained & validated |
| `2` | `manhole` | **UNSUPPORTED** | Excluded in Phase 03; never relabelled |
| Others | `waterlogging`, `damaged_patch`, etc. | **UNSUPPORTED** | Zero training data; reported as unassessed |

---

## 4. Usage Example

```python
from src.detection import HazardDetector

# Initialize detector with approved checkpoint
detector = HazardDetector()

# Run inference on an image path or array
result = detector.detect(
    image_input="data/pothole_crack_manhole/data/images/20250216_164521.jpg",
    image_id="frame_001",
    route_id="route_A",
    segment_id="seg_03",
    conf=0.25,
)

# Convert to JSON-serializable dictionary
result_dict = result.to_dict()
print(f"Status: {result.status.value}, Found: {len(result.detections)} hazards")

# Non-destructively visualise detections onto an artifact copy
detector.visualise(
    image_input="data/pothole_crack_manhole/data/images/20250216_164521.jpg",
    result=result,
    output_path="logs/evaluation/qualitative_samples/sample_output.jpg",
)
```

---

## 5. Limitations Note (TRD §7.4, Rule 20)

- **Monocular Depth Ambiguity:** Single uncalibrated 2D monocular dashboard camera images cannot provide true 3D metric depth, volume, or physical pothole depth without calibrated stereo sensors, LiDAR, or camera intrinsics.
- **Bounding Box Approximations:** Normalized bounding box extents indicate 2D image footprint, not volumetric road depression.
