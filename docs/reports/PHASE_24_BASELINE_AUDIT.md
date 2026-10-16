# SafeRoute AI — PHASE 24 Baseline Audit (READ-ONLY)

> **Date:** 2026-10-15 · **Workspace:** `D:\New folder (3)` · **Branch:** `main` (clean at start)
> **Type:** read-only baseline audit — no code, dataset, checkpoint, config, dependency or
> model was modified. No training was run.
> **Governing:** `master_rules.md` (authoritative, all 20 rules), `docs/TRAINING_RULES.md`,
> `docs/PRD.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md`.
> **Evidence rule:** a status is PASS only with evidence executed in *this* audit.
> Everything else is labelled *previously collected* (not re-verified here).

---

## 1. Scope & provenance

This report establishes the Phase-24 baseline for the remaining completion work
(dataset audit report, dataset cleaning, YOLO11 accuracy, real imagery / Mapillary,
four-route comparison, facilities, end-to-end testing). It is a **baseline only** —
no fixes were applied, and unrelated issues were intentionally left untouched.

- Repository HEAD at audit start: `5645dcb feat(phases-19-23b): live OSM stack, geocoding, API/LLM/frontend hardening; fix road-imagery integrity`
- Working tree at audit start: **clean** (`git status` → nothing to commit).

---

## 2. Commands executed in this audit (actual results)

| # | Command | Actual result |
|---|---|---|
| 1 | `git status` / `git branch --show-current` / `git log --oneline -10` | clean tree; branch `main`; HEAD `5645dcb` |
| 2 | `Test-Path docs\reports\PHASE_24A_DATASET_AUDIT.md` | **False (missing)** |
| 3 | `.\.venv\Scripts\python.exe -m unittest discover -s tests` | **Ran 148 tests — OK — exit code 0** (19.2 s warm run) |
| 4 | `Get-Content data\splits\{train,val,test}.txt` (line counts) | train **1406**, val **402**, test **201** |
| 5 | Read `config/detection.yaml`, `config/hazard_severity.yaml`, `data/dataset.yaml`, imagery/facilities configs | as cited below |
| 6 | Read `logs/evaluation/evaluation_record.json`, `logs/training/*/run_record.json` | v1/v2 run records present (hashes cited below) |

**Not executed (no approval / not applicable):** any live provider call (Nominatim,
OSRM, Overpass, Mapillary, Ollama), any dataset audit script, any training, any
download. These are not re-verified here.

---

## 3. Verified facts (measured this audit)

1. **Test suite:** `python -m unittest discover -s tests` → **148 tests, 0 failures,
   0 errors, exit code 0**. This confirms the "148 passed" figure for the current tree.
   (This supersedes the older "119 tests, 1 fail" figure in
   `docs/reports/COMPLETE_PROJECT_AUDIT.md`.)
2. **Active dataset & splits:** `data/pothole_crack_manhole/data` with split files
   `data/splits/{train,val,test}.txt` = **1406 / 402 / 201** images. Class mapping in
   `data/dataset.yaml`: `0: pothole`, `1: crack`; class `2 (manhole)` excluded/unsupported.
3. **Checkpoints present (unmodified):**
   - `models/training/saferoute-yolo11-v1/weights/best.pt` — sha256 `61F6EDA2…78E65` (from `evaluation_record.json`).
   - `models/training/saferoute-yolo11-v2/weights/best.pt` — sha256 `B6354A56…8800BA` (from `run_record.json`).
   - `weights/yolo26n.pt` — **unreferenced** by any config/code (provenance unverified).
4. **Serving model wiring:** `config/detection.yaml` → `model_version: saferoute-yolo11-v1`,
   `checkpoint: models/training/saferoute-yolo11-v1/weights/best.pt`. **v2 is not wired.**
5. **Confidence policy is now consistent:** `config/detection.yaml` `inference.conf = 0.25`
   and `config/hazard_severity.yaml` `thresholds.confidence_threshold = 0.25` agree
   (single-confidence policy, PHASE_22). `test_threshold_consistency` passes in the 148-test run.
6. **`.env` is absent** (`Test-Path .env` → False). Therefore live Mapillary imagery and
   live Ollama explanations are **OFF** by configuration; the app degrades to local archive
   / deterministic fallback, as documented.
7. **No `TODO/FIXME/NotImplemented/XXX/HACK` markers** remain in `src/`.
8. **Facilities config** lists hospital/pharmacy/petrol/hotel/police (see `config/facilities.yaml`);
   provider separation from the hazard score is documented (Rule 11).

## 4. Verified findings from previously collected evidence (NOT re-run this audit)

These are historical artefacts present on disk; their content was read but the
underlying measurements were **not** re-executed here (would require dataset reads /
external calls). They are labelled accordingly.

- **PHASE_03 dataset audit** (`docs/reports/PHASE_03_report.md`, `reports/phase03/*`):
  2,009 images / 2,009 YOLO labels; classes `{0:1261 pothole, 1:2519 crack, 2:957 manhole}`;
  0 malformed lines; 5 exact-duplicate groups (10 images); 118 content groups (356 images);
  **HIGH leakage risk** (94.9% are `vlcsnap-*` video frames, median 2 s gap). Licence:
  **CC BY 4.0** (attribution mandatory). *Previously collected.*
- **PHASE_20 RDD2022 audit** (`docs/reports/PHASE_20_rdd2022_verification.md`,
  `reports/phase20/*`): 30,224 train images / 30,224 XMLs, perfect pairing, 1 malformed
  `zero_area` box; mapped to project: crack 37,695 / pothole 6,083; extra labels excluded,
  never relabelled; duplicate scan: 1 exact group (2 images), 920 near-dup groups (4,266
  images). Licence: **conflicting (figshare CC BY 4.0 vs creators CC BY-SA 4.0)** →
  project conservatively adopts **CC BY-SA 4.0**. **Not converted / not merged / not trained on.**
  *Previously collected.*
- **v1 metrics** (`logs/evaluation/evaluation_record.json`): val mAP@0.5 = 0.2731,
  test mAP@0.5 = **0.2615** (pothole 0.2909 / crack 0.2321). *Previously collected.*
- **v2 metrics** (`docs/reports/PHASE_20_rdd2022_verification.md`): **val only** mAP@0.5 =
  0.287 (pothole 0.368 / crack 0.206); best epoch 104. **No held-out test evaluation → no
  improvement claim.** *Previously collected.*

---

## 5. Risks & observations (not fixed in this audit)

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| R1 | High | **`docs/reports/PHASE_24A_DATASET_AUDIT.md` is missing.** Phase 24A cannot be claimed complete. | `Test-Path` → False (this audit) |
| R2 | Medium | **Stale audit doc:** `COMPLETE_PROJECT_AUDIT.md` states "119 tests, 1 fail" and lists B1/B2 as open; current tree is 148/0 and B1 (threshold) / B2 (coverage/no-detections) appear addressed by PHASE_22/23. The historical doc contradicts current code. | §3.1, §3.5, `src/risk/aggregate.py`, `src/detection/schemas.py` |
| R3 | Medium | **v2 checkpoint trained but not wired and never test-evaluated**; no evidence v2 ≥ v1. Promotion must be evidence-based. | `config/detection.yaml`, §4 |
| R4 | Low | **Unreferenced weight** `weights/yolo26n.pt` (unknown provenance, git-ignored). | `grep yolo26` → no references |
| R5 | Medium | **Live external providers unverified in this audit** (Mapillary, Overpass, Ollama); `.env` absent. | §3.6 |
| R6 | Medium | **Leakage not eliminated** in the active dataset (video-frame dominated); split exists but residuals were disclosed at PHASE_03. | §4 PHASE_03 |
| R7 | Low | RDD2022 downloaded/audited but **not converted/merged** — its licence decision (CC BY-SA 4.0) is recorded but not yet actioned. | §4 PHASE_20 |
| R8 | Info | 65–75% completion estimate is a judgement, not a measurement; the baseline here is evidence-only. | master_rules Rule 14 |

---

## 6. Missing documentation / artefacts

- `docs/reports/PHASE_24A_DATASET_AUDIT.md` — **missing** (exact required path).
- No live-imagery verification artefact for Mapillary (no token, §3.6).
- No held-out test evaluation artefact for `saferoute-yolo11-v2`.
- No end-to-end real-world (live provider) test artefact for the current tree.

---

## 7. Proposed next work (each as a small, separately-approved phase)

1. **Phase 2 (24A audit report):** create `docs/reports/PHASE_24A_DATASET_AUDIT.md`
   consolidating PHASE_03/PHASE_20 evidence + this baseline. **Requires user approval**
   (Phase 2 of the task instructs to request approval before creating it).
2. **Phase 3 (dataset quality/leakage):** propose a reproducible cleaned split + manifest
   without deleting/overwriting originals. **No training.**
3. **Phase 4 (YOLO11 accuracy):** establish reproducible baseline, propose plan.
   **Stop before training for explicit approval.**
4. **Phase 5 (real imagery/Mapillary):** hermetic mock tests; live checks only with
   credentials + approval.
5. **Phase 6 (routes + facilities):** verify ≤4 genuine routes, consistent risk/route math,
   facilities separated from the hazard score.

> Phase 6 of the task prompt was **truncated** mid-sentence ("Risk comparisons use the
> same"). Its full requirements should be supplied before Phase 6 begins.

---

## 8. Non-action confirmation

- No model training, fine-tuning, dataset generation or checkpoint modification occurred.
- No dataset/label/weight/config/source file was modified, moved, or deleted.
- No package installed; no external/paid API called; no download performed.
- Only new file created by this audit: this report
  (`docs/reports/PHASE_24_BASELINE_AUDIT.md`).
