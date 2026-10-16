# SafeRoute AI — PHASE 24F: Detection Operating-Point Analysis & Leakage Audit

> **Phase:** PHASE 24F — measure the *shipped application* detection pipeline across
> confidence operating points for the existing **v1** and **v2** checkpoints, and audit
> whether the splits used for selection are genuinely held out.
> **Date executed:** 2026-10-16 (UTC) · **Workspace:** `D:\New folder (3)` · **Branch:** `main`
> **Mode:** **Evaluation only.** No training, fine-tuning, resume, weight change, checkpoint
> promotion/overwrite, config change, dataset/split change, dependency change, download,
> commit or push.
> **Governing rules:** `master_rules.md` 1, 5, 6, 7, 9, 14, 15, 16, 18, 19, 20.
> **Inputs:** `PHASE_24D_FRESH_HOLDOUT_EVALUATION.md`, `PHASE_24E_REAL_IMAGE_DETECTION.md`,
> `data/dataset.yaml`, `data/splits/*`, `data/dataset_v2.yaml`, `data/splits_v2/*`,
> `src/detection/detector.py`, `config/detection.yaml`, `config/hazard_severity.yaml`.

Evidence labels: **VERIFIED** (measured this phase) · **PARTIALLY VERIFIED** · **BLOCKED**.

---

## 1. Executive summary

**1. The reported PHASE 24D/24E "holdout" numbers are on training data for both checkpoints.**
The PHASE 24C derived splits were rebuilt **date-atomic** after v1/v2 were trained on the
**original random** split (`data/dataset.yaml`). Re-deriving membership shows (VERIFIED):

| Derived split | Images | Images that were in the ORIGINAL **train** split (seen by v1/v2) |
|---|---|---|
| derived `train` | 1,398 | 837 (60%) |
| derived `val` | 178 | **138 (77.5%)** |
| derived `test` | 216 | **216 (100%)** |

The derived `test` split is capture date `2025-02-26`, and the **original** train split
contains all 217 images of that date. Therefore PHASE 24E's "test" F1 = 0.604 and PHASE
24D's test mAP are **optimistically biased** and must not be presented as unseen-holdout
performance. **The only images v1/v2 never saw are the ORIGINAL `val`+`test` images
(601 images)** — 561 now sit inside derived `train` and 40 inside derived `val`.

**2. On the genuinely unseen 601-image set, real detection quality is much lower than
reported, and v2 has a modest, consistent F1/recall advantage over v1** (VERIFIED):

| Operating point (conf) | Micro P | Micro R | Micro F1 | pothole F1 | crack F1 | bg-images clean rate (149) |
|---|---|---|---|---|---|---|
| **v1 @ 0.25 (current serving)** | 0.346 | 0.260 | 0.297 | 0.352 | 0.261 | 0.282 |
| v1 @ 0.20 (v1 best F1) | 0.312 | 0.297 | 0.304 | 0.357 | 0.272 | 0.248 |
| **v2 @ 0.25** | 0.312 | 0.343 | 0.327 | 0.373 | 0.298 | 0.148 |
| **v2 @ 0.30 (v2 best F1)** | 0.341 | 0.319 | **0.329** | 0.373 | 0.303 | 0.188 |

**3. Threshold tuning alone does not measurably improve the current checkpoint.** v1's micro
F1 optimum on unseen data is t≈0.20 (F1 0.304) vs the configured 0.25 (0.297) — a +0.007
difference that costs precision and background cleanliness. Raising the threshold raises
precision and background cleanliness but **lowers recall**; the F1 curve is flat between
0.20 and 0.30.

**4. Per-class thresholds are not cleanly supported.** The app has a single
`inference.conf` that is also the aggregator threshold (PHASE 22 guard, `src/config/thresholds.py`),
so class-specific thresholds would require a detector code change, not a drop-in config edit.

**Recommendation (requires approval — not applied):** the smallest change with measurable
evidence is to **serve v2 instead of v1**. On the 601 unseen images v2 raises micro F1 from
**0.297 → 0.327** (+0.030) and recall from **0.260 → 0.343** at the current conf 0.25, but it
lowers precision (0.346 → 0.312) and worsens background-frame cleanliness (0.282 → 0.148).
If reducing background false positives is the priority, v2 at conf 0.30 gives F1 0.329 with
precision 0.341 and background clean-rate 0.188. **No production change was made.**

---

## 2. Scope and guardrails honoured

- Ran the shipped `HazardDetector` (`detect-v2`, `preprocess-v1`) — not raw `YOLO.predict`.
- Selected using **validation / leakage-controlled data only**. The derived `test` split was
  **not used for selection** (it is training data anyway).
- No training/fine-tuning/resume; no checkpoint promotion/overwrite; no config change; no
  dataset/label/split change; no dependency change; no download; no commit/push; no cleanup
  of unrelated files. All pre-existing untracked user files preserved.

---

## 3. How the app loads and runs the detector (VERIFIED by reading the source)

| Stage | Implementation | Value |
|---|---|---|
| Checkpoint | `src/detection/detector.py` `_load_model()` → `YOLO(checkpoint_path)`; path from `config/detection.yaml: model.checkpoint` | v1 `models/training/saferoute-yolo11-v1/weights/best.pt` |
| Missing checkpoint | Raises `FileNotFoundError`; **no silent fallback** (ARCHITECTURE §5.7) | — |
| model_version label | **Hard-coded module constant** `MODEL_VERSION = "saferoute-yolo11-v1"` | is **not** updated when another checkpoint is loaded |
| Preprocessing | `src/preprocessing/pipeline.py` `preprocess-v1`: validate → letterbox to 640×640, stride 32, pad 114, `INTER_LINEAR`; CLAHE disabled by default | letterbox, BGR |
| Inference | `model.predict(conf, iou, imgsz, max_det, augment, device)` | imgsz 640 |
| Confidence | `inference.conf` (single policy, shared with the aggregator) | **0.25** |
| NMS IoU | `inference.iou` | **0.45** |
| max_det | `inference.max_det` | 300 |
| augment (TTA) | `inference.augment` | false |
| device | `inference.device: null` → auto (CUDA if free) | — |
| Class mapping | `SUPPORTED_CLASSES = {0: pothole, 1: crack}`; other ids reported `unsupported_class_*` | two-class checkpoint |
| Box de-letterbox | subtract pad, divide by ratio, clamp to source; also emits normalized coords | — |
| Threshold consistency | `src/api/pipeline.py` + `src/config/thresholds.py` raise if `detection.conf != severity.confidence_threshold` | both 0.25 |

**Consequence for promotion:** because `MODEL_VERSION` is a code constant, swapping the
checkpoint to v2 is *not* a single-line config edit — it also requires updating the module
constant (and ideally `config/detection.yaml: metadata.model_version`). This is recorded as
part of the recommended-but-not-applied change.

---

## 4. PHASE 24E error patterns (existing evidence, re-read)

At the serving point (conf 0.25, match IoU 0.5) on the 216-image derived test set:

| Class | GT | Pred | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|---|---|
| pothole | 98 | 149 | 48 | 101 | 50 | 0.322 | 0.490 | 0.389 |
| crack | 292 | 266 | 195 | 71 | 97 | 0.733 | 0.668 | 0.699 |
| overall (micro) | 390 | 415 | 243 | 172 | 147 | 0.586 | 0.623 | 0.604 |

*(These test numbers are training-contaminated — §1.)* Dominant patterns computed this
phase from `false_positives.csv` / `missed_detections.csv`:

- **Background false positives are the largest error class.** 55/172 FPs are on frames with
  **no** GT box (41 pothole, 14 crack). 36/46 hazard-free frames fired at least once.
- **FPs are not only low-confidence.** Median FP confidence ≈ 0.42 (pothole) / 0.39 (crack);
  43 pothole and 20 crack FPs have conf ≥ 0.5 (max 0.87). Pothole TP and FP confidence
  distributions **overlap** (TP mean 0.494 vs FP mean 0.483), so confidence alone cannot
  separate pothole TPs from FPs. Crack separates better (TP mean 0.586 vs FP mean 0.430).
- **~44% of FPs co-occur with a match in the same image (75/172).** These are extra/duplicate
  boxes on already-detected hazards (NMS IoU 0.45 lets overlapping duplicates through).
- **Pothole FPs are small boxes** (median 1,562 px²) vs **crack FPs large** (6,361 px²).
- **Missed detections are mostly genuine non-detections**, not localisation drift: 142/147
  misses had no same-class box within IoU 0.5 (only 5 were "right box, wrong class", all
  pothole←crack). Missed potholes are small (median GT area 650 px²); missed cracks are
  large (median 3,770 px²) and often had no nearby prediction at all (37/97).

**Limitation:** the agent driving this phase cannot view images, so representative annotated
frames were inspected via the machine-readable FP/FN/cross-class records and the per-image
JSON, **not** by pixel inspection. Visual confirmation of the above remains open.

---

## 5. Selection evidence (leakage-controlled)

### 5.1 Derived val split (`data/splits_v2/val.txt`) — 178 images, 475 boxes

Full-val sweep (VERIFIED, `reports/phase24f_verify/`). **Caveat: 138/178 images were seen in
training**, so these absolute numbers are inflated; provenance subsets are the honest view.

| conf | v1 micro P/R/F1 | v2 micro P/R/F1 |
|---|---|---|
| 0.15 | 0.458 / 0.526 / 0.490 | 0.447 / 0.606 / 0.515 |
| 0.20 | 0.556 / 0.482 / 0.516 | 0.524 / 0.560 / 0.541 |
| **0.25 (config)** | **0.632 / 0.438 / 0.517** | **0.589 / 0.541 / 0.564** |
| 0.30 | 0.686 / 0.364 / 0.476 | 0.638 / 0.512 / **0.568** |
| 0.35 | 0.752 / 0.314 / 0.443 | 0.684 / 0.474 / 0.560 |

Provenance split (the current script's `provenance_sweep`):

| Provenance subset | n | v1 F1 @0.25 | v2 F1 @0.25 |
|---|---|---|---|
| original train (seen) | 138 | 0.590 | 0.642 |
| original val (unseen) | 21 | 0.405 | 0.388 |
| original test (unseen) | 19 | 0.244 | 0.356 |
| **unseen combined** | **40** | **0.345** | **0.376** |

### 5.2 Leakage-free 601-image set (the primary selection set)

Definition: every derived image whose stem is in the ORIGINAL `val` or `test` split
(561 from derived train + 40 from derived val). 601 images, **1,017 GT boxes** (362 pothole,
655 crack), **149 background-only images**. Read-only harness:
`scripts/audit/phase24f_clean_holdout.py`.

| conf | v1 micro P/R/F1 | v2 micro P/R/F1 |
|---|---|---|
| 0.15 | 0.264 / 0.334 / 0.295 | 0.245 / 0.398 / 0.304 |
| 0.20 | 0.312 / 0.297 / **0.304** | 0.277 / 0.368 / 0.316 |
| **0.25 (config)** | 0.346 / 0.260 / 0.297 | 0.312 / 0.343 / 0.327 |
| 0.30 | 0.385 / 0.226 / 0.285 | 0.341 / 0.319 / **0.329** |
| 0.35 | 0.429 / 0.203 / 0.276 | 0.352 / 0.280 / 0.312 |

Per-class and background detail at 0.25 / 0.30:

| Option | pothole P/R/F1 | crack P/R/F1 | background clean rate |
|---|---|---|---|
| v1 @ 0.25 | 0.365 / 0.340 / 0.352 | 0.331 / 0.215 / 0.261 | 0.282 (42/149 clean) |
| v2 @ 0.25 | 0.336 / 0.420 / 0.373 | 0.296 / 0.301 / 0.298 | 0.148 (22/149 clean) |
| v2 @ 0.30 | 0.362 / 0.384 / 0.373 | 0.327 / 0.282 / 0.303 | 0.188 (28/149 clean) |

**Reading.** v2 is a **higher-recall, lower-precision** model: it catches markedly more
potholes and cracks (pothole F1 0.373 vs 0.352; crack F1 0.298 vs 0.261) but also produces
*more* background false positives. Raising the single threshold from 0.25 to 0.30 recovers
some precision and background cleanliness on v2 while leaving F1 essentially unchanged
(0.327 → 0.329). **The v2 F1 advantage is consistent across every set evaluated** (601 unseen,
40 unseen, 178 mixed, and the 24D test), but it is modest (≈ +0.03 F1).

### 5.3 Test-split discipline

The PHASE 24E report already examined the derived test split, so it is not pristine; and
§1 shows it is training data for v1/v2. It was **not used for threshold or model selection**
in this phase. Any number quoted from 24D/24E must carry the contamination disclosure.

---

## 6. Cross-device reproducibility check

The pre-existing untracked sweep (`reports/phase24f/`, CPU) and this phase's re-run
(`reports/phase24f_verify/`, GPU, CUDA free 6.90 GiB) gave **identical counts at conf 0.25**:

| | v1 TP/FP/FN | v2 TP/FP/FN |
|---|---|---|
| existing (CPU) | 208 / 121 / 267 | 257 / 179 / 218 |
| re-run (GPU) | 208 / 121 / 267 | 257 / 179 / 218 |

At the low floor (0.05) counts differ by 0–2 boxes (GPU/CPU non-determinism). The serving
point is stable across device. The sweep's own equivalence check
(`direct_verification.counts_match`) was **True** for both checkpoints in both runs.

---

## 7. Recommendation and required approval

**Recommendation (smallest measurable change): serve v2 instead of v1, keeping the single
confidence at 0.25.** Evidence: on 601 genuinely-unseen images it improves micro F1
(0.297 → 0.327) and recall (0.260 → 0.343), and per-class F1 (pothole 0.352 → 0.373,
crack 0.261 → 0.298), at the cost of precision (0.346 → 0.312) and background cleanliness
(0.282 → 0.148). If the priority is background false positives, **v2 @ 0.30** is the better
operating point (F1 0.329, precision 0.341, background clean 0.188), at a small recall cost
(0.343 → 0.319).

**Do not change the threshold on v1:** v1 is already at/near its F1 optimum at 0.25; t=0.20
gives +0.007 F1 while worsening precision and background FPs. A higher threshold is **not**
automatically better — it trades recall for precision and barely moves F1.

**Not recommended:** per-class thresholds (unsupported: single `inference.conf` shared with
the aggregator via the PHASE 22 guard; would require a detector code change).

**This change was NOT applied.** Promotion requires explicit approval and would touch:
`config/detection.yaml: model.checkpoint` (+ `metadata.model_version`) and the hard-coded
`MODEL_VERSION` string in `src/detection/detector.py`. A follow-up confirmation on a truly
fresh holdout (a capture date/session not used for either model's training) is strongly
advised before bidding any accuracy number.

---

## 8. Commands run, results and runtime (VERIFIED)

```powershell
# Relevant application test suite (detection, detection outcome, preprocessing, threshold consistency, E2E)
.\.venv\Scripts\python.exe -m unittest tests.unit.test_detection tests.unit.test_detection_outcome `
    tests.unit.test_preprocessing tests.unit.test_threshold_consistency tests.integration.test_end_to_end_pipeline
# -> Ran 34 tests in 22.778s  OK  (exit 0)

# Re-run the existing sweep (new out-dir; existing reports/phase24f/ left untouched), GPU
.\.venv\Scripts\python.exe scripts\audit\phase24f_confidence_sweep.py --checkpoint v1 --split val --verify-conf 0.25 --out-dir reports\phase24f_verify   # 34.8s
.\.venv\Scripts\python.exe scripts\audit\phase24f_confidence_sweep.py --checkpoint v2 --split val --verify-conf 0.25 --out-dir reports\phase24f_verify   # 17.6s

# Leakage-controlled holdout over the 601 unseen images (new read-only harness)
.\.venv\Scripts\python.exe scripts\audit\phase24f_clean_holdout.py --checkpoint v1 --device auto   # 41.8s, 601 imgs
.\.venv\Scripts\python.exe scripts\audit\phase24f_clean_holdout.py --checkpoint v2 --device auto   # 33.0s, 601 imgs
```

All runs reported `content_unchanged = True` (checkpoint hashes, derived-label Merkle,
configs, split files) and `counts_match = True`.

---

## 9. Files created this phase (all NEW; nothing existing overwritten)

```
scripts/audit/phase24f_clean_holdout.py                 (new read-only eval harness)
reports/phase24f_verify/v1_val_sweep.json               \
reports/phase24f_verify/v1_val_operating_points.csv      |  re-run of the existing sweep
reports/phase24f_verify/v2_val_sweep.json                |  into a NEW directory
reports/phase24f_verify/v2_val_operating_points.csv     /
reports/phase24f_verify_v1_console.log                  (new)
reports/phase24f_verify_v2_console.log                  (new)
reports/phase24f_verify_clean/v1_clean_sweep.json       \
reports/phase24f_verify_clean/v1_clean_operating_points.csv  |  601-image leakage-free eval
reports/phase24f_verify_clean/v2_clean_sweep.json        |
reports/phase24f_verify_clean/v2_clean_operating_points.csv /
docs/reports/PHASE_24F_CONFIDENCE_SWEEP.md              (this report)
```

**Modified:** none (0 tracked files changed). **Pre-existing untracked `reports/phase24f/`
files were left byte-identical** (timestamps still 02:51/02:52). Both checkpoints unchanged:
v1 `61F6EDA2…8078E65`, v2 `B6354A56…DF8800BA`. Nothing committed or pushed.

---

## 10. Limitations (honest)

1. **Small clean sample for provenance subsets** (40 images) — wide uncertainty; the 601-image
   set is larger but still one dataset family (vlcsnap dashcam frames).
2. **Filename-derived capture sessions** (PHASE 24C W1): dates are a proxy, not verified
   session identity. The original random split is the ground truth for "seen in training".
3. **Device**: the 601-image and re-run sweeps used the GPU; the pre-existing sweep used CPU.
   Conf counts match at 0.25, but sub-threshold boxes can differ by 0–2.
4. **No pixel-level image inspection** by this agent (cannot view images); FP/FN patterns come
   from the recorded CSVs/JSON.
5. **Single operating point per metric**: these are thresholded P/R/F1 at match IoU 0.5, not
   mAP; not directly comparable to PHASE 24D's Ultralytics mAP at conf 0.001.
6. **Absolute accuracy is low on unseen data** (micro F1 ≈ 0.30–0.33, background clean-rate
   0.15–0.28). This is a submission risk independent of the v1/v2 choice and cannot be fixed
   by threshold tuning alone (would need training/retraining, out of scope).

---

## 11. Stop condition

No production change applied. `config/detection.yaml` still serves **v1** at conf **0.25**.
Awaiting explicit approval before any checkpoint promotion, threshold change, or detector
code change. See §7 for the exact proposed edits.
