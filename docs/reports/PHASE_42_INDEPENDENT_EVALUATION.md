# PHASE 42 / P1 — Independent YOLO11 v2 Detector Evaluation

> **Phase status:** Harness complete and audited; real independent evaluation **NOT_ASSESSED**
> **Date:** 2026-11-10 (P1 recovery audit added)
> **Branch/HEAD:** `main` @ `b3ee84f` plus uncommitted P1 audit files
> **Environment:** Windows 11, Python 3.12.10, torch 2.13.0+cu130, CUDA available
> (NVIDIA GeForce RTX 5050 Laptop GPU), ultralytics 8.4.163, opencv 4.14.0, numpy 2.5.3

---

## 1. Executive status

Phase 42 built an **evaluation-first** harness for the serving YOLO11 v2 detector.
P1 adds an **artifact-recovery audit** that searches the filesystem, hashes every
model candidate, inspects the available corpora, and writes the three required
machine-readable artifacts in an explicitly blocked state.

**No accuracy, safety, or deployment-readiness claim is made.** The genuine
`saferoute-yolo11-v2` checkpoint is absent, and no independently collected,
session-disjoint, annotated dataset exists locally. The real independent
evaluation is therefore **NOT_ASSESSED**, not PASS, CONDITIONAL, or FAIL.

Newly measured in P1 (this session):

| Item | Result |
|---|---|
| Full regression suite after P1 changes | **434 tests OK in 23.212 s** (423 prior + 11 new) |
| Checkpoint candidates found on `D:\` and `C:\Users\pushk` (≥1 MB, `.pt/.pth/.onnx/.engine`) | 6; **none** matches the pinned v2 hash |
| Canonical v2 path hash | `19619F99…60B916D0` = **same file as P0 smoke and v1** (5,443,482 bytes, smoke marker present) |
| Documented historical v2 hash | `B6354A56…8800BA` — **no matching file exists** in the searched roots |
| Production config pins | unchanged (`detection 22371AE8…B18344`, `severity D11AA0F7…CDF473`) |
| Default evaluation preflight | **refused** the smoke substitute, exit code `2` |
| Candidate overlap probe (98 Mapillary vs 2,009 local reference images) | 0 exact, 0 near-duplicate cross matches; 7 internal candidate groups (18 images) |
| Detector inference for the real model | **not executed** |
| Detector metrics for the real model | **none; null, not zero** |

The smoke substitute must never be reported as v2. No substitute weights were
loaded to produce any metric.

---

## 2. Scope and safety guardrails

Phase 42 evaluates **detector evidence reliability only**. It does not certify
SafeRoute AI as safe for public deployment.

Explicit non-changes (verified by hashes, see §6):

- `src/risk/engine.py` is unchanged.
- The risk formulas are unchanged:
  `H_i = Σ severity / max(km, 0.1)` and `S_i = 100 · e^(−0.10 · H_i)`.
- `config/detection.yaml` and `config/hazard_severity.yaml` are unchanged.
- The serving checkpoint is never overwritten or modified by evaluation.
- The P0 smoke marker `P0_SMOKE_SUBSTITUTE.json` was **not** removed or bypassed.
- `.env`, Mapillary tokens, and other secrets are not read or emitted.
- Route replay is **offline research only** and does not alter production
  recommendation behavior.

---

## 3. Readiness assessment

| Requirement | State | Evidence |
|---|---|---|
| Genuine `saferoute-yolo11-v2` serving checkpoint | **NOT AVAILABLE** | Canonical path holds the P0 smoke substitute (`sha256 19619F99…60B916D0`, 5,443,482 bytes) with `P0_SMOKE_SUBSTITUTE.json` present |
| Independent, session-disjoint imagery + labels | **NOT AVAILABLE** | `data/independent/` does not exist; no separate-session road collection exists |
| Independent annotation policy + A/B QC + adjudication | **NOT AVAILABLE** | No independent manifest/QC record exists |
| Reference-corpus session registry | **NOT AVAILABLE** | `split_manifest.csv` has filename-derived `capture_date` but **no `session_id` column** |
| Verified distance / route metadata | **NOT AVAILABLE** | No `distance_km`, `route_id`, `segment_id`, or route ground truth |
| Production inference configuration | **AVAILABLE** | Verified below (`imgsz=640`, `conf=0.25`, `iou=0.45`, `max_det=300`, classes pothole/crack) |
| Single-confidence contract | **VERIFIED** | `detection.yaml inference.conf = 0.25` equals `hazard_severity.yaml thresholds.confidence_threshold = 0.25` |
| Evaluation harness + blocked audit | **COMPLETE** | `src/evaluation/` + `scripts/evaluate_independent.py` + `scripts/audit/phase42_p1_artifact_audit.py` |
| Runtime environment | **AVAILABLE** | CUDA GPU present; ultralytics/OpenCV/numpy importable |

Because the checkpoint and independent data are missing, **no real evaluation
could be executed**. This is a data/artifact availability failure, not a detector
result.

---

## 4. Production inference contract verified

| Setting | Required | Loaded | Status |
|---|---|---|---|
| `imgsz` | 640 | 640 | PASS |
| `inference.conf` | 0.25 | 0.25 | PASS |
| `inference.iou` | 0.45 | 0.45 | PASS |
| `max_det` | 300 | 300 | PASS |
| Trained classes | 0=pothole, 1=crack | 0=pothole, 1=crack | PASS |
| `hazard_severity.thresholds.confidence_threshold` | 0.25 | 0.25 | PASS |
| Checkpoint path | `models/training/saferoute-yolo11-v2/weights/best.pt` | Present but smoke substitute | **REFUSED** |

Artifact hashes recorded during this phase:

| Artifact | SHA-256 |
|---|---|
| `config/detection.yaml` | `22371AE8C1DA3CBA77E40EE096337915D16C0CFDDB9E7E2AF9213F4BE1B18344` |
| `config/hazard_severity.yaml` | `D11AA0F73511E4EEF4B49869D2D009F5F06048801A1B03A64ED5CDB407CDF473` |
| Configured checkpoint (smoke substitute) | `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` |
| Documented historical v2 (not present) | `B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA` |
| Documented historical v1 (not present) | `61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65` |

Any drift in the first two values makes the evaluation reject or fail
reproducibility. The historical hashes are provenance pins from
`reports/phase24d/v2_metrics.json`, `reports/phase24d/holdout_verification.json`,
and the Phase 20/24D/project-audit documents; they are evidence that a genuine
artifact once existed, not proof that it is present now.

> Observed pre-existing documentation drift: `config/hazard_severity.yaml`
> still declares `metadata.model_version: saferoute-yolo11-v1` while
> `config/detection.yaml` declares `saferoute-yolo11-v2`. It does not affect the
> confidence contract and was **not modified** in Phase 42 or P1.

---

## 5. P1 artifact recovery audit

### 5.1 What was searched

| Scope | Detail |
|---|---|
| Roots | `D:\` and `C:\Users\pushk` |
| Suffixes | `.pt`, `.pth`, `.onnx`, `.engine` |
| Minimum size | 1,000,000 bytes |
| Excluded directory names | `.git`, `.venv`, `__pycache__`, `node_modules`, `site-packages` |
| Additional manual searches | archives (`.zip/.7z/.rar/.tar/.gz`), recycle bins, git objects and dangling commits, `*.pt` under `C:\Users\pushk`, directories matching `saferoute|New folder|backup|archive` |
| Result | **6 model candidates; 0 matches** for the pinned v2 hash |

The six candidates (all newly hashed in P1):

| Path | Bytes | SHA-256 |
|---|---|---|
| `models/training/p0-smoke/weights/best.pt` | 5,443,482 | `19619F99…60B916D0` |
| `models/training/p0-smoke/weights/last.pt` | 5,443,482 | `7BA35DF6…DDF8D5BC` |
| `models/training/saferoute-yolo11-v1/weights/best.pt` | 5,443,482 | `19619F99…60B916D0` |
| `models/training/saferoute-yolo11-v2/weights/best.pt` (canonical) | 5,443,482 | `19619F99…60B916D0` |
| `yolo11n.pt` (pretrained) | 5,613,764 | present, non-v2 |
| `weights/yolo26n.pt` (pretrained) | 5,544,453 | present, non-v2 |

The canonical v2 path, the v1 path, and the P0 smoke `best.pt` are the **same
file content**. The canonical path additionally carries
`P0_SMOKE_SUBSTITUTE.json`, whose own text states the original checkpoint was not
recoverable and must not be used for safety claims or production evaluation.

### 5.2 Why the smoke file is refused

`scripts/evaluate_independent.py --preflight-only` raises
`MODEL INTEGRITY ERROR` and exits `2` when the marker is present. There is no
default path that converts the smoke model into v2 evidence. The explicit
`--allow-smoke-substitute` flag exists only for harness wiring checks and forces
`harness_only = true` plus `NOT_ASSESSED`.

### 5.3 Corpus inventory

| Corpus | Images | Labels | Status |
|---|---|---|---|
| `data/derived_2class/images` | 2,009 | 1,792 | Same-source CC BY 4.0 dashcam derivative; train 1,398 / val 178 / test 216. **Not independent.** |
| `data/pothole_crack_manhole/data/images` | 2,009 | 2,009 (YOLO) | Original same-source corpus; **not independent** |
| `data/imagery/mapillary` | 98 | 0 | Unannotated candidate corpus under CC-BY-SA 4.0 per config; **not evaluation evidence** |
| `data/independent/` | — | — | **Absent** |

### 5.4 Candidate overlap probe (exploratory only)

| Measurement | Result |
|---|---|
| Candidate images vs reference images | 98 vs 2,009 |
| Exact SHA-256 cross matches | **0** |
| Perceptual-hash cross pairs at Hamming ≤ 8 | **0** |
| Internal candidate near-duplicate groups | **7 groups / 18 images** (largest group 5) |
| Elapsed | 6.038 s |

Methods: SHA-256 exact file hash, 64-bit DCT perceptual hash, Hamming distance
≤ 8. A clean cross-corpus result means the cached Mapillary candidates do not
duplicate the local reference images. It does **not** make them independent
evaluation data: they are unannotated, lack session/provenance/QC evidence, and
are far below the 1,500–3,000 image target. No leakage clearance is claimed.

### 5.5 Local split integrity (same-source only)

`data/splits_v2/split_manifest.csv` contains 2,009 rows with a filename-derived
`capture_date`; no `capture_date` spans multiple splits, so the date-atomic proxy
passes. This is recorded as **PASS for the proxy only**. It is same-source data
and does not establish independence from any external corpus. The manifest has
**no `session_id` column**, so video/camera adjacency cannot be excluded.

---

## 6. Acceptance gate status for the real v2 model

The blocked audit writes seven gates. No gate is upgraded by substitute evidence.

| Gate | Status | Reason |
|---|---|---|
| Dataset independence | **NOT_ASSESSED** | No independent dataset; sessions/provenance/reference separation unverifiable |
| Annotation reliability | **NOT_ASSESSED** | No independent annotation policy, version, A/B review, or adjudication |
| Reproducibility | **NOT_ASSESSED** | Config/checkpoint hashes recorded, but no genuine checkpoint/dataset pair exists to freeze |
| Metric completeness | **NOT_ASSESSED** | Stage B not run; metrics are `null` with an explicit reason |
| Production parity | **NOT_ASSESSED** | Stage B cannot run against the genuine v2 checkpoint |
| Decision impact | **NOT_ASSESSED** | No route ground truth; replay not run |
| Safety honesty | **PASS** | The audit reports no accuracy, no route result, no deployment claim |

`Safety honesty` passes because the artifact is explicitly a blocked audit:
`evaluation_executed = false`, `metrics.overall = null`, `metrics.per_class =
null`, `stage_a.ran = false`, `stage_b.ran = false`. It does **not** convert any
other gate to PASS for the real model.

---

## 7. Harness validation evidence

### 7.1 Automated tests

Before P1 changes (fresh baseline):

```
python -m unittest discover -s tests -v
→ Ran 423 tests in 36.518s
→ OK
```

After P1 changes (fresh, final):

```
python -m unittest discover -s tests -v
→ Ran 434 tests in 23.212s
→ OK
```

The 11 new tests are `tests/unit/test_artifact_audit.py`. Command output is
captured at `C:\Users\pushk\AppData\Local\Temp\opencode\p1_unittest_final.log`.
(The PowerShell `Tee-Object` pipeline reports process exit code 1 after a
successful text pipeline; unittest itself reports `OK`.)

### 7.2 New P1 tests

| Test | Guarantee |
|---|---|
| `test_historical_hashes_are_pinned` | v1/v2 pins are present and distinct |
| `test_smoke_checkpoint_is_refused_and_not_reported_as_v2` | Smoke file never becomes v2; status `NOT_ASSESSED`; metrics `null` |
| `test_missing_checkpoint_and_dataset_are_explicit` | Missing checkpoint/dataset produce explicit blockers |
| `test_missing_split_manifest_is_not_reported_as_date_atomic_pass` | Absent manifest is `NOT_ASSESSED`, not `PASS` |
| `test_checkpoint_search_hashes_candidates` | Candidate discovery hashes real files |
| `test_candidate_overlap_detects_exact_duplicate` | Exact-duplicate detection works |
| `test_candidate_overlap_detects_near_duplicate` | Perceptual near-duplicate detection works |
| `test_candidate_overlap_reports_disjoint_images` | Disjoint corpora report zero matches |
| `test_write_audit_artifacts_writes_three_blocked_reports` | Three required artifacts written, all `NOT_ASSESSED` |
| `test_audit_does_not_modify_configs_or_checkpoint` | Before/after hashes unchanged |
| `test_genuine_and_complete_inputs_refuse_blocked_report` | Blocked audit refuses when genuine inputs are detected |

### 7.3 Negative tests inherited from the Phase 42 harness

- Missing serving checkpoint → explicit `ModelIntegrityError`.
- P0 smoke substitute → explicit `SmokeSubstituteError`; harness-only run is
  forced to `NOT_ASSESSED`.
- Empty evaluation split → `EmptyDatasetError`.
- Missing label file → `MissingAnnotationError`; never an implicit negative.
- Malformed, non-finite, non-positive, out-of-range, or inverted boxes → rejected.
  Human YOLO labels may overshoot a boundary by at most 1% because center/size
  encoding is rounded; that rounding is clamped to the image edge. Larger
  excursions and all production prediction boxes remain strictly rejected.
- Unsupported annotation/detection class → rejected or excluded and disclosed.
- Confidence-contract drift, non-production `imgsz`, or config mutation →
  `ProductionParityError` / reproducibility FAIL.
- Below-threshold production detections and invalid prediction boxes → parity FAIL.
- Missing class support → `insufficient_sample`, not a fabricated perfect score.
- Evaluation does not modify the serving checkpoint or production configs.

### 7.4 Live preflight evidence (executed in P1)

Default preflight (no override):

```
python scripts/evaluate_independent.py --preflight-only
→ MODEL INTEGRITY ERROR: The configured checkpoint is the non-production P0
  smoke substitute (marker: ...\P0_SMOKE_SUBSTITUTE.json).
→ exit code 2
```

Explicit harness-only preflight:

```
python scripts/evaluate_independent.py --preflight-only --allow-smoke-substitute
→ "harness_only": true
→ "is_smoke_substitute": true
→ "sha256": "19619F99...60B916D0"
→ PREFLIGHT OK — checkpoint 19619F99...60B916D0
→ exit code 0
```

The harness-only result describes the smoke model, not the real
`saferoute-yolo11-v2` serving model, and produces no metrics.

### 7.5 Historical harness-only integration smoke (Phase 42 session, not re-run in P1)

During the Phase 42 harness session, the CLI was run once in harness-only mode on
the same-source derived test split to validate Stage B wiring. This is a
**historical, non-independent** result and is not a v2 accuracy measurement.
Structural outcomes recorded then: 216/216 images inferred, 0 failures, 26
detections on 24 images, 0 unsupported/below-threshold/invalid detections,
coverage 1.0, 390 ground-truth boxes (98 pothole, 292 crack), 0 session ids,
FP/km `None`. It is retained only as wiring evidence.

---

## 8. Dataset requirements for a real evaluation

### Independence

- New imagery from sessions/cameras/geography outside the training corpus.
- Whole collection sessions must remain on one side of any split; no session may
  cross train/val/test.
- Exact duplicates and DCT perceptual-hash near-duplicates are checked. A
  duplicate spanning sessions is an error; a duplicate within one session is a
  warning that frames are not independent observations.
- A reference session list and/or reference imagery must be supplied to prove
  separation from the training corpus.

### Layout and labels

```text
data/independent/
  dataset.yaml                 # path + test split + names {0: pothole, 1: crack}
  images/test/*.jpg
  labels/test/*.txt            # one .txt per image; empty file = verified negative
  manifests/
    independent_manifest.json
    collection_sessions.csv    # required for session identity
    training_sessions.csv      # reference-session registry
```

YOLO label format is `class center_x center_y width height`, normalized to the
original image. A missing label file is an error; use an empty file for a
verified negative, and only when the manifest confirms it. Class IDs outside
`{0, 1}` are rejected. A boundary-touching box may round at most 1% of the image
dimension outside `[0, 1]` from center/size encoding; that rounding is clamped to
the edge. Larger excursions are rejected.

### Manifest fields

`independent_manifest.json` should record at minimum:

- `dataset_version`, `annotation_version`;
- `provenance` (collection source, dates, geography, cameras, sessions);
- `annotation` (policy/guideline path, version);
- `quality_control` (`annotator_a`, `annotator_b`, `adjudication`, agreement);
- `images[]` with `image_id`, `file`, `session_id`, `condition`,
  `route_id`, `segment_id`, `segment_length_m`, and verified `distance_km`
  where FP/km is to be reported.

Without sessions, provenance, and reference separation, the dataset-independence
gate stays NOT_ASSESSED or CONDITIONAL — never PASS.

### Sample size and coverage

Target ~1,500–3,000 annotated images including potholes, cracks, both-class
images, difficult negatives, and diverse geography/conditions. Sources must be
used only with permission or a compatible licence. Any external download,
licence acceptance, new collection, or annotation labour requires approval.

---

## 9. Generated artifacts

All three required JSON artifacts were generated in P1 in a blocked state:

| Artifact | Status | Key content |
|---|---|---|
| `reports/phase42_independent_evaluation.json` | `NOT_ASSESSED` | 7 gates, null metrics, blockers, recovery request, completion checklist |
| `reports/phase42_leakage_audit.json` | `NOT_ASSESSED` | 6 leakage checks, corpus inventory, candidate overlap probe, limitations |
| `reports/phase42_artifact_manifest.json` | `NOT_ASSESSED` | Checkpoint search + hashes, config pins, dataset/evaluation-code hashes, integrity block |

Integrity block recorded in the manifest:

```json
{
  "before": {"checkpoint_sha256": "19619F99...60B916D0", "...": "..."},
  "after":  {"checkpoint_sha256": "19619F99...60B916D0", "...": "..."},
  "mutation_detected": false,
  "production_config_unchanged_since_phase42_harness": true,
  "serving_checkpoint_modified": false,
  "production_scoring_modified": false,
  "secrets_read": false
}
```

These files contain **no detector measurement**. `null` means "not measured",
never "zero performance".

---

## 10. How to run once real artifacts exist

```powershell
# 1. Verify the genuine checkpoint and production contract
.\\.venv\\Scripts\\python.exe scripts\\evaluate_independent.py --preflight-only

# 2. Freeze and evaluate the independent split
.\\.venv\\Scripts\\python.exe scripts\\evaluate_independent.py `
  --dataset-yaml data/independent/dataset.yaml `
  --manifest data/independent/manifests/independent_manifest.json `
  --reference-sessions data/independent/manifests/training_sessions.csv `
  --reference-image-dir data/derived_2class/images `
  --output reports/phase42_independent_evaluation.json
```

Exit codes:

- `0` — report produced (PASS / CONDITIONAL / NOT_ASSESSED)
- `1` — report produced with FAIL
- `2` — input/integrity error (missing checkpoint, smoke substitute, config
  drift, invalid/empty dataset)

The genuine checkpoint must replace the smoke substitute at
`models/training/saferoute-yolo11-v2/weights/best.pt` **and** the smoke marker
JSON must be removed by the operator who restores it. Any file that is not the
genuine accepted artifact must not be reported as v2.

To regenerate only the blocked audit:

```powershell
.\\.venv\\Scripts\\python.exe scripts\\audit\\phase42_p1_artifact_audit.py `
  --search-root "D:\\" --search-root "C:\\Users\\pushk"
```

---

## 11. Metrics the real report will contain

- Checkpoint SHA-256, config hashes, dataset image/label/combined hashes, and
  environment (Python, torch, ultralytics, OpenCV, numpy, CUDA device).
- Stage A metrics and per-class AP50, with the validation-semantics caveat.
- Stage B prediction/inference counts, failures, excluded unsupported classes,
  below-threshold and invalid detections.
- Per-class and overall AP50 / AP50-95, precision, recall, F1, TP/FP/FN.
- Miss rate by class and by condition group (daylight/night/rain/etc.).
- FP/km only with verified distance; raw and heuristic frame-deduplicated counts.
- Wilson and session-clustered bootstrap confidence intervals.
- `insufficient_sample` where class/session support is too small.
- Offline route replay: score deltas, rank changes/reversals, rank correlation,
  and research-only eligibility changes. Production recommendation remains
  untouched.

None of these exist for the real model today.

---

## 12. Known limitations and honesty notes

1. **No v2 metrics exist.** The genuine v1/v2 checkpoints were unrecoverable
   after the environment move; the current path is a clearly marked P0 smoke
   substitute. Historical Phase 40 numbers (`mAP50=0.0423`, `mAP50-95=0.0121`,
   precision `0.114`, recall `0.094`, pothole AP50 `0.070`, crack AP50 `0.015`)
   were produced from the former `D:\New folder (3)` workspace and were **not
   reproduced** here.
2. **Historical Phase 24D numbers are same-source** and are not independent
   evidence.
3. **No independent dataset exists.** The derived two-class dataset is
   same-source and must not be relabelled as independent.
4. **Stage A ≠ Stage B.** Ultralytics validation and serving inference do not
   necessarily apply `conf`/NMS identically; Stage B is authoritative.
5. **FP/km needs distance.** Frame counts are not kilometres. The deduplicated
   FP count is heuristic and is reported beside, not instead of, the raw count.
6. **No arbitrary mAP pass threshold.** Phase 42 gates on process and integrity,
   not on an invented accuracy cut-off.
7. **Small samples are marked, not hidden.** Undefined AP for a missing class is
   `None` + `insufficient_sample`, never `0.0` or `1.0` by assumption.
8. **Route replay is research-only.** It reuses the production aggregator and
   engine unchanged and does not alter production recommendations.
9. **The candidate overlap probe is exploratory.** A clean result on 98
   unannotated images does not establish independence or leakage clearance.
10. **Secrets were not accessed.** No `.env` or Mapillary token was read,
    printed, or committed.

---

## 13. Files added or changed in P1

| File | Change |
|---|---|
| `src/evaluation/artifact_audit.py` | New blocked-audit module: checkpoint search/hashing, corpus inspection, overlap probe, blocked artifacts, refusal when genuine inputs exist |
| `scripts/audit/phase42_p1_artifact_audit.py` | New CLI that writes the three blocked artifacts |
| `tests/unit/test_artifact_audit.py` | New 11-test suite for the audit |
| `reports/phase42_independent_evaluation.json` | Generated (blocked, `NOT_ASSESSED`, null metrics) |
| `reports/phase42_leakage_audit.json` | Generated (blocked, `NOT_ASSESSED`) |
| `reports/phase42_artifact_manifest.json` | Generated (blocked, `NOT_ASSESSED`) |
| `docs/reports/PHASE_42_INDEPENDENT_EVALUATION.md` | This report, updated with P1 evidence |

Phase 42 harness files (unchanged in P1) remain: `src/evaluation/__init__.py`,
`matching.py`, `metrics.py`, `confidence_intervals.py`, `dataset_validation.py`,
`leakage.py`, `evaluator.py`, `route_replay.py`,
`scripts/evaluate_independent.py`, and the five harness test modules.

No production model, risk engine, risk formula, preprocessing, or production
configuration was modified.

---

## 14. Conclusion

The Phase 42 harness and P1 audit are complete and tested. The harness correctly
refuses the smoke substitute, rejects config drift, and cannot silently turn
missing labels, empty datasets, unsupported classes, or invalid boxes into
favourable metrics. The blocked audit cannot emit metrics at all.

The real independent evaluation of `saferoute-yolo11-v2` is **NOT_ASSESSED**:

- genuine serving checkpoint: missing (only the smoke substitute occupies the
  canonical path; documented v2 hash `B6354A56…8800BA` has no matching file);
- independent, session-disjoint, annotated dataset: missing;
- independent annotation/QC/session evidence: missing;
- verified distance and route ground truth: missing.

No detector accuracy, safety, or deployment-readiness claim is supported until
the genuine checkpoint and an independent dataset are supplied and evaluated with
the command in §10.
