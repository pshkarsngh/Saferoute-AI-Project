# 05 — Preprocessing and Feature Engineering

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Related:** [`04-dataset-and-labeling.md`](04-dataset-and-labeling.md) ·
> [`06-ml-models-and-algorithms.md`](06-ml-models-and-algorithms.md) ·
> [`02-architecture-and-data-flow.md`](02-architecture-and-data-flow.md)

---

## 1. The preprocessing contract

`src/preprocessing/pipeline.py` (459 lines) is the **single, versioned** image pipeline
for the whole project.

| Attribute | Value |
|---|---|
| Module | `src/preprocessing/pipeline.py` |
| Version string | `__version__ = "preprocess-v1"` |
| Class | `PreprocessingPipeline` |
| Public methods | `validate_image()`, `letterbox()`, `preprocess()`, `prepare_inference_input()` |
| Status vocabulary | `ImageStatusCode` — `ok`, `empty`, `unreadable`, `corrupt`, `unsupported`, `too_small`, `low_quality` |
| Result type | `ImageStatus` (frozen dataclass: `code`, `is_valid`, `path`, `width`, `height`, …) |
| Governing rule | Rule 6 — "consistent, documented preprocessing pipeline" |

The version string is propagated into inference results
(`ImageDetectionResult.pipeline_version`), so any stored detection can be traced to the
exact preprocessing behaviour that produced it.

## 2. Validation stage — `validate_image()`

The pipeline's first responsibility is to **reject bad images honestly** rather than
passing them downstream as if they were clean.

| Check | Outcome on failure | Rationale |
|---|---|---|
| File exists / is a file | `unreadable` | |
| File size > 0 | `empty` | A zero-byte file is not a "no hazards" image — it is a missing image. |
| `cv2.imread` succeeds | `unreadable` | Decode failure. |
| Decoded array is not `None` | `unreadable` | |
| Array has usable dimensions | `too_small` | Below the configured minimum. |
| Array is non-degenerate | `corrupt` | |
| Shape/dtype acceptable (e.g. channel count) | `unsupported` | |

**Rule 9 consequence.** A rejected image never becomes "no hazards detected". It becomes
an explicit status that reduces coverage and is disclosed to the user. The distinction
between "we looked and found nothing" and "we could not look" is preserved end to end.

The `ImageStatus` dataclass is frozen, so a validated status cannot be mutated after
the fact.

## 3. Geometric preparation — `letterbox()`

| Aspect | Implementation |
|---|---|
| Method | Aspect-ratio-preserving letterbox (pad, do not stretch) |
| Pad value | Constant fill colour applied to the padded region |
| Output size | Configured inference size (640 × 640 by default, `config/detection.yaml` `inference.imgsz`) |
| Why | Matches Ultralytics' own inference-time geometry so the network sees the geometry it was trained on. |

**TRD §7.1 compliance.** "Avoid duplicating preprocessing Ultralytics already performs."
The project resolves this by *replicating* the letterbox geometry in its own
deterministic, unit-tested module while allowing Ultralytics to perform the final
tensor conversion. `tests/unit/test_preprocessing.py` (11 test methods) locks the
geometry down.

## 4. Inference preparation — `prepare_inference_input()`

Produces the NumPy array handed to the detector. The pipeline returns the image plus
metadata describing what was done, so `HazardDetector` can rescale bounding boxes back
to original-image pixel coordinates without guessing.

## 5. Rule 6 — training/inference consistency, stated honestly

Rule 6 requires a consistent preprocessing pipeline for training **and** inference, with
any divergence documented.

**What is shared.** Image validation, colour handling (BGR for OpenCV I/O throughout),
and the letterbox geometry.

**What is deliberately not shared.** The training path uses Ultralytics' built-in
augmentation (mosaic, flips, HSV shifts, etc.). Those augmentations are a
*training-time* concern; replicating them at inference time would corrupt the
determinism requirement (Rule 14/17) and reduce reproducibility.

This is a documented, justified divergence rather than an unnoticed inconsistency. The
practical consequence is stated plainly: **the detector is trained on augmented imagery
and served on un-augmented imagery**, which is the standard practice but does mean
val/test metrics measure the augmented-trained model under clean conditions.

## 6. `src/detection/detector.py` — inference, not feature engineering

`HazardDetector` (422 lines, `__version__ = "detect-v2"`, `MODEL_VERSION =
"saferoute-yolo11-v2"`) performs:

1. **Checkpoint resolution.** `DEFAULT_CHECKPOINT_REL =
   Path("models/training/saferoute-yolo11-v2/weights/best.pt")`, overridable through
   `config/detection.yaml` → `model.checkpoint`. A missing checkpoint produces an
   explicit failure status; it never silently falls back to a different model.
2. **Class filtering.** `SUPPORTED_CLASSES = {0: "pothole", 1: "crack"}`. Any class
   outside this map is reported as `unsupported_class` (Rule 5).
3. **Inference.** `imgsz 640`, `conf 0.25`, `iou 0.45`, `max_det 300`, `augment: false`
   (TTA off), `batch 1`, `device: null` (auto: CUDA if available, else CPU).
4. **Bounding-box rescaling.** Detections are mapped back to original-image pixel
   coordinates and simultaneously normalised to `[0, 1]` — both forms are stored
   (`bbox_xyxy` and `bbox_norm`), matching the TRD §8.1 contract.
5. **Visualisation.** `visualise()` draws boxes, labels and confidences onto a **copy**;
   source images are never overwritten (TRD §7.2).
6. **Timing.** `ImageDetectionResult.timing_ms` records per-stage timing.

### 6.1 The confidence-threshold policy

`config/detection.yaml` → `inference.conf: 0.25`
`config/hazard_severity.yaml` → `thresholds.confidence_threshold: 0.25`

These two values **must** be equal. `src/config/thresholds.py::assert_threshold_consistency()`
reads both files and raises if they diverge by more than `1e-9`.

**Why this module exists.** The config comments record the original defect: the detector
once ran at `conf 0.15` while the aggregator ran at `0.25`. Every detection in the
`[0.15, 0.25)` band was produced, then silently discarded — producing "zero hazards →
score 100". The fix was a single, enforced policy with a loud failure mode.
`tests/unit/test_threshold_consistency.py` (4 test methods) guards it.

## 7. Severity policy — `src/risk/severity.py` (Rule 5, 7, 12)

`SeverityPolicy` is a pure, config-driven function. It never consults the LLM.

### 7.1 Base severity table (`config/hazard_severity.yaml`)

| Class | Base severity | Rationale recorded in the config |
|---|---:|---|
| `pothole` | 3.0 | Direct mechanical shock, tyre-puncture risk, loss of vehicle stability |
| `crack` | 1.5 | Surface defect causing minor traction degradation, precursor to road decay |
| `unsupported` | 1.0 | Fallback for a class with no configured severity |

Scale: **1.0 (minor) → 5.0 (critical)**.

### 7.2 Modulation

`modulation.enabled: true`, with `alpha_confidence: 0.25`, `beta_area: 0.50`,
`min_severity: 1.0`, `max_severity: 5.0`.

```
area_norm  = clamp(bbox_width_norm × bbox_height_norm, 0, max_bbox_area_norm)
area_factor = 1.0 + beta_area     × (area_norm / max_bbox_area_norm)
conf_factor = 1.0 + alpha_confidence × (confidence − confidence_threshold)
severity    = clamp(base_severity × area_factor × conf_factor, min_severity, max_severity)
```

Every severity value is therefore fully reconstructible from the config plus the
detection attributes — the TRD §8.2 requirement, satisfied exactly.

### 7.3 Additional thresholds

| Key | Value | Purpose |
|---|---:|---|
| `dedup_iou_threshold` | 0.45 | Spatial IoU above which two detections of the same class are treated as one object |
| `min_bbox_area_norm` | 0.0001 | Rejects degenerate boxes |
| `max_bbox_area_norm` | 0.30 | Caps the area influence of the modulation |

## 8. Aggregation features — `src/risk/aggregate.py`

`HazardAggregator.assess_segment()` converts raw detections into segment-level hazard
records.

| Function | Purpose |
|---|---|
| `compute_iou(box1, box2)` | Intersection-over-Union of two `[x1, y1, x2, y2]` boxes |
| `deduplicate_adjacent_segment_hazards(...)` | Prevents the same physical hazard being counted on both sides of a segment boundary |
| `HazardAggregator.assess_segment(...)` | Applies the confidence threshold, severity policy and IoU de-duplication, then derives the segment status |

### 8.1 Adjacent-segment de-duplication

`config/risk_engine.yaml` → `hazard_metric.dedup_adjacent_segments: true`,
`adjacent_boundary_iou: 0.50`.

The same pothole photographed in two overlapping segments would otherwise be counted
twice, inflating the hazard density of a boundary. The IoU test identifies the duplicate
and keeps one instance. This is the TRD §9.4 requirement, implemented.

### 8.2 Segment status rules

`config/hazard_severity.yaml` → `status_rules`:

| Rule | Value | Meaning |
|---|---:|---|
| `full_coverage_threshold` | 1.0 | 100 % of images processed → `assessed` |
| `partial_coverage_min` | 0.01 | > 0 % and < 100 % → `partially_assessed` |
| `unassessed_status` | `unassessed` | 0 % of images available |
| `failed_status` | `failed` | Decode or pipeline crash |

## 9. Risk features — `src/risk/engine.py`

### 9.1 The formula

```
S_i = 100 × exp(−λ × H_i)
```

| Symbol | Definition | Source |
|---|---|---|
| `S_i` | Safety score for unit *i* (0–100, higher = safer) | `config/risk_engine.yaml` `scoring` |
| `H_i` | Hazard density: total severity ÷ max(length_m / 1000, `min_segment_length_km`) | `config/risk_engine.yaml` `hazard_metric` |
| `λ` | `lambda_decay: 0.10` | `config/risk_engine.yaml` `scoring.lambda_decay` |

Segment normalisation uses `min_segment_length_km: 0.10` and
`default_segment_length_m: 100.0`, so short segments are not penalised purely for being
short.

### 9.2 The features the engine actually consumes

1. **Verified detections** — class, confidence, severity, bounding box.
2. **Segment length** — normalises hazard density.
3. **Image coverage** — `CoverageInfo(images_total, images_used, fraction)`.
4. **Acquisition status** — `AssessmentStatus` per segment.

### 9.3 Coverage suppression (Rule 9)

`config/risk_engine.yaml` → `coverage_policy`:

| Key | Value | Effect |
|---|---:|---|
| `min_coverage_threshold` | 0.50 | Below this the segment's score is **suppressed** (`is_suppressed = True`). |
| `full_coverage_threshold` | 0.90 | Above this the segment is fully `assessed`. |
| `suppress_insufficient_coverage` | true | Enables the suppression above. |
| `unassessed_score_placeholder` | `null` | An unassessed segment is assigned **no score at all** — never `100.0`. |

`SegmentScoreResult` (in `src/risk/schemas.py`) makes suppression explicit through the
`is_suppressed: bool` field and by allowing `segment_score: Optional[float] = None`.
`RouteSafetyResult` carries `coverage`, `status`, `limitations`, `hazards_total`,
`detection_outcome` and `safety_note` alongside the score.

### 9.4 Configuration hash — traceability

`src/risk/engine.py::compute_config_hash()` computes a SHA-256 over the risk-engine
config file and stores it as `config_hash` on every `RouteSafetyResult`, on every
`analyses` row and on every `scores` row. Any score can be traced to the exact policy
that produced it (Rule 17).

### 9.5 Determinism

`DeterministicRiskEngine` is a pure function of its inputs. It has no I/O, no clock
dependence in the scoring path, no randomness and no LLM involvement. The same inputs
always yield the same output, which is what makes the score a *measurement* rather than
a guess.

## 10. Comparison features — `src/risk/comparison.py`

`RouteComparer.build()` operates on the scores **already computed** by the engine. It
never computes, alters or invents a score (Rule 7).

| Feature | Purpose |
|---|---|
| `assessed_length_fraction()` | The fraction of a route's **length** that actually carries a score (not merely the fraction of segments). This is the metric that decides whether a recommendation is defensible. |
| Minimum assessed fraction | A route must be sufficiently assessed before it can be recommended. |
| Demo-imagery exclusion | Routes scored from imagery not geographically matched to the requested roads are excluded from the real-world recommendation (Rules 9, 20). |
| Stale-imagery exclusion | Routes whose imagery is stale are excluded. |
| Tie handling | **Tied top scores produce no recommendation** — the evidence does not support declaring one route safer (Rule 14: never fabricate a preference). |
| Unassessed exclusion | An unassessed route is never ranked or presented as safe (Rule 9). |

`tests/unit/test_route_recommendation_correctness.py` (15 test methods) and
`tests/unit/test_route_comparison.py` (14 test methods) lock these behaviours down.

## 11. Feature-engineering assessment

**What is strong**

- Every derived quantity is traceable to a named config key. There are no magic numbers
  in the scoring path.
- Severity is a closed-form function of detection attributes — auditable line by line.
- Coverage is a first-class input, not a footnote, and insufficient coverage *suppresses*
  rather than inflates.
- Duplicates at segment boundaries and within frames are handled explicitly.
- A configuration hash is carried end to end into the database.

**What is weak or missing**

| Gap | Consequence |
|---|---|
| No explicit severity calibration against ground-truth severity labels | `λ = 0.10` is a *provisional baseline* (the config says so), and the base-severity table is a reasoned judgement, not a measured calibration. The score is **ordinal and comparable between routes**, but it is not a calibrated probability of harm. |
| `H_i` sums severity without a spatial-extent term beyond area modulation | Two small potholes score the same as one large one of equal total severity; this is a deliberate simplicity, but it is a modelling choice. |
| Coverage uses *image count* per segment, and the assessed fraction uses *length* | Both are reasonable, but the two are not reconciled in one metric; the comparison layer uses length-weighted coverage while the segment layer uses count-based coverage. |
| No uncertainty band on the score | The score is presented as a point estimate; coverage is the only confidence signal shown to the user. |
| Imagery timestamps are frequently missing in live data | Freshness cannot be verified, so live analyses resolve to `cannot_determine` (F-20). |
| No perspective/scale calibration | TRD §7.4 is explicit that a single uncalibrated monocular image cannot yield metric depth or area; the system honours this by not claiming physical dimensions. |

---

*All thresholds, formula constants and function names in this document were read from
`config/*.yaml` and the cited source files on 2026-10-21. No configuration file or source
file was modified.*
