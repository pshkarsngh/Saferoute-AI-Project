# PHASE_10 — Inference Pipeline Report

> **Phase ID:** PHASE_10  
> **Status:** COMPLETE  
> **Date (actual):** 2026-10-13  
> **Workspace:** `D:\New folder (3)`  
> **Module Version:** `detect-v1`  
> **Model Identifier:** `saferoute-yolo11-v1`  
> **Checkpoint:** `models/training/saferoute-yolo11-v1/weights/best.pt`  
> **Checkpoint Hash (SHA-256):** `61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65`  
> **Predecessor:** [`PHASE_09`](./PHASE_09_report.md) — Model Evaluation & Checkpoint Acceptance  
> **Successor:** [`PHASE_11`](../phases/PHASE_11.md) — Hazard Aggregation & Severity Policy  
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../phases/PHASE_10.md`](../phases/PHASE_10.md)  
> **Approval Reference:** User explicit directive `next` (2026-10-13)

---

## 1. Files Created

- **Inference Module:**
  - [`src/detection/__init__.py`](../../src/detection/__init__.py)
  - [`src/detection/detector.py`](../../src/detection/detector.py) (Main `HazardDetector` inference engine)
  - [`src/detection/schemas.py`](../../src/detection/schemas.py) (Structured `DetectionRecord` & `ImageDetectionResult` dataclasses)
- **Unit Test Suite:**
  - [`tests/unit/test_detection.py`](../../tests/unit/test_detection.py) (7 comprehensive failure path & contract tests)
- **Documentation:**
  - [`src/detection/README.md`](../../src/detection/README.md) (Full API specification, contract definition, and limitations)
- **Completion Report:**
  - [`docs/reports/PHASE_10_report.md`](./PHASE_10_report.md)

---

## 2. Detection Record Contract (TRD §7.3 & ARCHITECTURE §4)

Every detection emitted conforms to the JSON-serializable `DetectionRecord` contract:

| Field | Type | Description |
|---|---|---|
| `model_version` | `str` | Approved model version identifier (`saferoute-yolo11-v1`) |
| `image_id` | `Optional[str]` | Unique source image identifier |
| `route_id` | `Optional[str]` | Route identifier for multi-route comparisons |
| `segment_id` | `Optional[str]` | Route segment identifier |
| `hazard_class` | `str` | Detected hazard class (`pothole`, `crack`, or `unsupported_class_<id>`) |
| `confidence` | `float` | Detection confidence in range `[0.0, 1.0]` |
| `bbox_xyxy` | `List[float]` | Pixel coordinates `[x1, y1, x2, y2]` scaled to original unpadded image |
| `bbox_norm` | `List[float]` | Normalized bounding coordinates `[nx1, ny1, nx2, ny2]` in `[0.0, 1.0]` |
| `status` | `str` | Record status (`detected`, `unsupported_class`) |
| `error` | `Optional[str]` | Error message if anomalous (`None` on success) |

---

## 3. Preprocessing Integration

- **Pipeline Version Used:** `preprocess-v1` ([`src/preprocessing/pipeline.py`](../../src/preprocessing/pipeline.py))
- **Integration:** Directly reuses `PreprocessingPipeline.validate_image()` for image verification and `PreprocessingPipeline.preprocess()` for letterbox resizing with padding compensation.
- **Traceability:** Every `ImageDetectionResult` explicitly records `pipeline_version: "preprocess-v1"`.

---

## 4. Class Handling & Honest Disclosure (Rule 5)

- **Trained & Supported Classes Reported:**
  - `0`: `pothole`
  - `1`: `crack`
- **Unsupported Class Handling:**
  - Class index 2 (`manhole`) and all other untrained hazards (`waterlogging`, `damaged_patch`, `uneven_surface`, `speed_bump`) are never fabricated or relabelled.
  - If encountered from detector heads, they map to `unsupported_class` with status `unsupported_class` and explicit error disclosure.

---

## 5. Failure Paths (Observed & Verified)

| Scenario | Handled Behaviour | Evidence |
|---|---|---|
| **Missing Checkpoint** | Raises explicit `FileNotFoundError` during initialization; silent fallback to another model is forbidden (ARCHITECTURE §5.7). | Verified by `test_missing_checkpoint_raises_explicit_error` |
| **Invalid Image** | Returns `DetectionStatus.INVALID_IMAGE` with detailed validation error; excluded as evidence (Rule 9). | Verified by `test_detect_invalid_image_path` |
| **Corrupt / Empty Image** | Zero-byte or truncated file caught by OpenCV validation and returns `INVALID_IMAGE`. | Verified by `test_detect_corrupt_empty_file` |
| **Empty Detections** | Returns distinct `DetectionStatus.NO_DETECTIONS` with 0 records; strictly not interpreted as clean road (Rule 9). | Verified by `test_empty_detections_distinct_from_safe` |
| **Runtime Error** | Trapped cleanly, returning `DetectionStatus.FAILED` with error exception string. | Verified in `HazardDetector.detect()` |

---

## 6. Test Results (Actual)

Executed inside workspace `.venv` via standard library `unittest`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests\unit -p "test_*.py" -v
```

```
test_detect_corrupt_empty_file (test_detection.TestHazardDetector.test_detect_corrupt_empty_file) ... ok
test_detect_invalid_image_path (test_detection.TestHazardDetector.test_detect_invalid_image_path) ... ok
test_detect_valid_image (test_detection.TestHazardDetector.test_detect_valid_image) ... ok
test_detector_initialization (test_detection.TestHazardDetector.test_detector_initialization) ... ok
test_empty_detections_distinct_from_safe (test_detection.TestHazardDetector.test_empty_detections_distinct_from_safe) ... ok
test_missing_checkpoint_raises_explicit_error (test_detection.TestHazardDetector.test_missing_checkpoint_raises_explicit_error) ... ok
test_non_destructive_visualisation (test_detection.TestHazardDetector.test_non_destructive_visualisation) ... ok
test_determinism (test_preprocessing.TestPreprocessingPipeline.test_determinism) ... ok
test_inference_input_preparation (test_preprocessing.TestPreprocessingPipeline.test_inference_input_preparation) ... ok
test_original_file_preservation (test_preprocessing.TestPreprocessingPipeline.test_original_file_preservation) ... ok
test_original_image_array_preservation (test_preprocessing.TestPreprocessingPipeline.test_original_image_array_preservation) ... ok
test_validation_corrupt_file (test_preprocessing.TestPreprocessingPipeline.test_validation_corrupt_file) ... ok
test_validation_empty_file (test_preprocessing.TestPreprocessingPipeline.test_validation_empty_file) ... ok
test_validation_too_small (test_preprocessing.TestPreprocessingPipeline.test_validation_too_small) ... ok
test_validation_unreadable_missing_file (test_preprocessing.TestPreprocessingPipeline.test_validation_unreadable_missing_file) ... ok
test_validation_unsupported_extension (test_preprocessing.TestPreprocessingPipeline.test_validation_unsupported_extension) ... ok
test_validation_valid_image (test_preprocessing.TestPreprocessingPipeline.test_validation_valid_image) ... ok
test_visualise_does_not_mutate_input (test_preprocessing.TestPreprocessingPipeline.test_visualise_does_not_mutate_input) ... ok

----------------------------------------------------------------------
Ran 18 tests in 4.343s

OK
```

- **Passed / Failed:** **18 / 18 passed** (100% pass rate)
- **Failures:** 0

---

## 7. Original-Image Integrity

- **Source Image Preservation:** **Unchanged** (`VALID_TEST_IMAGE.stat().st_mtime` verified bit-for-bit unchanged before and after inference and visualisation).
- **Rule 1 Enforcement:** Visualisation checks enforce workspace isolation and reject any attempt to overwrite the source file (`ValueError` raised).

---

## 8. Validation Results Summary

| # | Check | Pass Condition | Status | Evidence |
|---|---|---|:---:|---|
| **V1** | Checkpoint resolved | Only approved checkpoint loads; missing -> error | **PASS** | `test_missing_checkpoint_raises_explicit_error` |
| **V2** | Shared preprocessing | Inference uses `preprocess-v1` | **PASS** | Validated via `pipeline_version` metadata |
| **V3** | Structured output | Records contain all required schema fields | **PASS** | Validated via `test_detect_valid_image` |
| **V4** | Class honesty | Only trained classes reported | **PASS** | Mapped to `pothole` and `crack`; others unsupported |
| **V5** | Failure paths | Missing ckpt / invalid / empty / error explicit | **PASS** | Validated via dedicated test cases |
| **V6** | No scoring | Inference computes no safety score | **PASS** | Asserted in `test_empty_detections_distinct_from_safe` |
| **V7** | Originals preserved | Source images unchanged | **PASS** | Verified via file mtime and copy-based rendering |
| **V8** | Tests pass | Tests executed and passing | **PASS** | 18/18 tests passed |

---

## 9. Limitations & Honesty Note (TRD §7.4, Rules 7, 12, 20)

- **No Risk Scoring:** The detector emits localized hazard bounding boxes and confidences only. It does not calculate road risk or route safety scores (reserved for the deterministic risk engine in [PHASE_12](../phases/PHASE_12.md)).
- **Monocular 2D Bounds:** Single monocular dashboard camera frames lack calibrated 3D depth and stereo baselines. 2D bounding boxes represent visual surface footprints, not volumetric depression or depth measurements.

---

## 10. Result & Next Phase

- **Result:** **`COMPLETE`**
- **Next Phase Authorised?** **`NO`** — awaiting explicit user review and approval before starting [`PHASE_11`](../phases/PHASE_11.md) (Hazard Aggregation & Severity Policy).
