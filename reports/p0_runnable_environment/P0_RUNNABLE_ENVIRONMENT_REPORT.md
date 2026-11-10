# P0 — Runnable Environment Restoration Report

**Project:** SafeRoute AI
**Date:** 2026-11-10
**Scope:** Make the existing project reproducibly runnable without changing the
architecture or weakening any of the 20 master rules.
**Result:** **P0 acceptance criteria met**, with three explicitly disclosed
substitutions (smoke checkpoint, no Ollama, stale imagery coverage). Nothing is
claimed that the evidence does not support.

---

## 1. Verdict

| Area | Outcome |
|---|---|
| Python + virtualenv + dependencies | Restored |
| `.env` configuration | Restored (git-ignored, token only) |
| Detection checkpoint | **Substituted** — original unrecoverable, marked non-production smoke model |
| Dataset / config path portability | Repaired (no more `D:/New folder (3)`) |
| Threshold consistency (0.25 = 0.25) | Verified |
| Test suite | **351 tests, OK** (21.791 s) |
| Application start + UI | Verified (`http://127.0.0.1:8000/`) |
| `/api/health` | `status: ok` |
| End-to-end analysis | Verified live (geocode → routes → imagery → detection → risk → explanation) |

The application runs, serves its UI, and produces a complete, rule-compliant
analysis using live Mapillary imagery, live OSRM routing, live Nominatim
geocoding and live Overpass facilities. The single behavioural caveat is that
every Mapillary frame available for the tested corridor is older than the
180-day freshness policy, so the backend **correctly refuses to recommend a
route** rather than presenting stale evidence as current (Rule 9).

---

## 2. What was restored

### 2.1 Python, virtualenv and dependencies

- Python **3.12.10** installed at `%LOCALAPPDATA%\Programs\Python\Python312`.
- Fresh `.venv` created in the workspace and all pinned `requirements.txt`
  dependencies installed successfully.
- CUDA is available: `NVIDIA GeForce RTX 5050 Laptop GPU`, PyTorch built for
  `cu130`.

| Package | Version |
|---|---|
| torch | 2.13.0+cu130 |
| torchvision | 0.28.0+cu130 |
| ultralytics | 8.4.163 |
| opencv-python | 4.14.0.94 |
| numpy | 2.5.3 |
| PyYAML | 6.0.3 |

### 2.2 Configuration

- `.env` created from `.env.example`.
- The file is **git-ignored** (`.gitignore:2`) and now contains only the single
  non-empty key `MAPILLARY_ACCESS_TOKEN`. Blank placeholder keys were removed:
  blank `KEY=` entries were being placed into `os.environ` as empty strings and
  were masking legitimate environment overrides (this was the root cause of one
  settings test failure).
- `load_settings()` confirms:
  - `imagery_source = mapillary`, `mapillary_token_present = True`
  - the token is **absent** from `to_safe_dict()` / `/api/config` output
  - routing `multi`, facilities `overpass`, geocoding `nominatim`
  - host `127.0.0.1`, port `8000`

### 2.3 Detection checkpoint (substitution, disclosed)

The original `saferoute-yolo11-v1` and `-v2` checkpoints are **not present in
this workspace and could not be recovered**. Per the agreed P0 approach, a
temporary smoke model was trained so the serving path could be exercised:

- Script: `scripts/p0_smoke_train.py` (new, reproducible, run from workspace root)
- Output: `models/training/p0-smoke/weights/best.pt`
- 8 epochs, `imgsz=640`, `batch=8`, `seed=0`, `device=cuda:0`, 335.4 s
- Validation: 178 images / 475 instances, **mAP50 0.115, mAP50-95 0.0386**
- Size 5,443,482 bytes, SHA-256
  `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0`
- Provenance: `models/training/p0-smoke/P0_SMOKE_MODEL.json`

The same file is installed at the two canonical serving paths the code and tests
expect:

- `models/training/saferoute-yolo11-v1/weights/best.pt`
- `models/training/saferoute-yolo11-v2/weights/best.pt`

Each canonical directory contains a loud marker,
`P0_SMOKE_SUBSTITUTE.json`, recording `status:
NON_PRODUCTION_P0_SMOKE_SUBSTITUTE`, the original-artifact warning, source and
installed hashes, and the smoke metrics. `/api/health` therefore reports
`model_version: saferoute-yolo11-v2` **because the smoke file occupies that
path**, not because the original v2 artifact was recovered. Do not cite the
0.115 mAP50 as production performance.

### 2.4 Path portability repair

The repository contained machine-specific absolute paths
`D:/New folder (3)/...` in executable configuration and scripts. Dataset splits
and configs now resolve from the workspace root:

- `data/dataset.yaml` and `data/dataset_v2.yaml`: `path: .` with
  `data/splits...` / `data/splits_v2...` split entries.
- All six split files rewritten to workspace-relative POSIX paths
  (3,801 lines; 0 missing images, 0 missing labels, no train/val/test overlap).
- Hard-coded roots replaced with file-relative resolution in:
  `scripts/train_baseline.py`, `scripts/evaluate_baseline.py`,
  `scripts/verify_yolo_opencv.py`, `scripts/prepare_datayolo_2class.py`,
  `scripts/prepare_rdd2022_yolo.py`, `scripts/audit/phase03_dataset_audit.py`,
  `scripts/audit/phase20_duplicate_scan.py`,
  `scripts/audit/phase20_rdd2022_audit.py`,
  `scripts/audit/phase24d_evaluate_holdout.py`,
  `tests/unit/test_detection.py`, `tests/unit/test_hazard_aggregation.py`.
- `train_baseline.py` / `evaluate_baseline.py` now `chdir` to the workspace root
  because Ultralytics resolves relative dataset entries against the CWD.
- `phase24d` converts relative split entries to absolute paths before file
  checks; the E2E test resolves split lines against the workspace root.
- `data/derived_2class/MANIFEST.json` intentionally still contains the original
  absolute paths: it is **historical provenance**, not executable config, and was
  not rewritten (Rule 20 — do not falsify recorded provenance).

### 2.5 Demo sample archive

`logs/evaluation/qualitative_samples/` (git-ignored) was missing, which caused
the demo/unmatched imagery tests to fail. It was restored with six frames copied
verbatim from `data/splits/test.txt` plus a `README.md` documenting that they are
demo-only, coordinate-less, and can never be matched to a real route segment.

---

## 3. Verification evidence

### 3.1 Threshold consistency

- `config/detection.yaml` → `conf: 0.25`
- `config/hazard_severity.yaml` → `confidence_threshold: 0.25`
- `tests/unit/test_threshold_consistency.py`: **4/4 pass** (matching values,
  policy loader agreement, runtime guard accepts consistent and rejects
  inconsistent configs).

### 3.2 Test suite

```
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
Ran 351 tests in 21.791s
OK
```

Before the repairs the suite failed on: missing approved checkpoint (2
`setUpClass` errors), missing demo-sample archive (4 imagery-integrity
failures), `MISSING` vs `UNMATCHED` status (2 failures), blank `.env` keys
breaking override precedence (1 failure), and workspace-relative split
resolution in the E2E test. All are resolved; no test was skipped, deleted, or
weakened.

### 3.3 Application start

```
.\.venv\Scripts\python.exe scripts\run_app.py --no-browser --port 8000
```

Startup banner reported `routing=multi imagery=mapillary facilities=overpass
geocoding=nominatim llm=on mapillary_token=yes`. `/api/health` answered within
~0.7 s:

```json
{
  "status": "ok",
  "model_version": "saferoute-yolo11-v2",
  "config_hash": "61B8143B42DF7FA76D2FF53902D4509D864D75B2705898FB32466E1559621D01",
  "providers": {"routing": "multi", "imagery": "mapillary",
                "facilities": "overpass", "geocoding": "nominatim", "llm": "ollama"},
  "capabilities": {"geocoding": true, "live_imagery": true, "live_llm": true}
}
```

Note: `live_llm: true` reflects that the LLM is **configured/enabled**; it is
not a liveness probe. No Ollama server is running, and the explainer therefore
reports `source: fallback` (see §3.5).

### 3.4 Endpoint exercise (live network except where noted)

Full machine-readable evidence: `reports/p0_runnable_environment/ENDPOINT_EVIDENCE.json`.

| Endpoint | Result | Time |
|---|---|---|
| `GET /api/config` | 200, token redacted (`mapillary_token_present: true`) | — |
| `POST /api/geocode` | 200, "Connaught Place, New Delhi" → 28.63177, 77.21938 (Nominatim) | 1,296 ms |
| `POST /api/routes` | 200, 2 OSRM routes (4,963 m / 485 s; 6,308 m / 605 s) | 1,074 ms |
| `POST /api/facilities` | 200, 164 live OSM facilities within 1,000 m | 45,275 ms |
| `POST /api/analyze` | 200, `partially_assessed`, id `an-16f14c72dbbd` | 31,999 ms |
| `GET /api/analyze/{id}` | 200, full record | 132 ms |
| `GET /api/analysis/{id}/hazards` | 200, `hazards_count: 0` | 5 ms |
| `GET /api/analysis/{id}/comparison` | 200, 2 ranked, `cannot_determine` | 5 ms |
| `GET /api/analysis/{id}/explanation` | 200, `source: fallback`, 2 routes referenced | 5 ms |
| `GET /api/analyze/an-doesnotexist` | **404** (correct) | 15 ms |
| `GET /` (UI) | 200, built React app (`INDROUTE`) | 26 ms |
| `GET /assets/*.js`, `*.css`, `/favicon.svg` | 200 (1,585,746 / 152,651 / 9,522 bytes) | — |

Facilities is slow (45.3 s) because the public Overpass instances are congested,
but it completed inside the configured 60 s query deadline using the mirror list
(`overpass.openstreetmap.fr` → `overpass-api.de` → `overpass.kumi.systems`).

### 3.5 Analysis detail (real run)

Route: 28.6139, 77.2090 → 28.63177, 77.21938 (Connaught Place, New Delhi).

| Timing | ms |
|---|---|
| Routing | 901.0 |
| Imagery acquisition | 17,177.6 |
| Detection | 7,695.9 |
| Risk scoring | 0.7 |
| Comparison | 0.1 |
| Explanation | 2,016.7 |
| Route explanations | 2,016.1 |
| **Total** | **31,524.5** |

| Route | Distance | Score | Coverage | Assessed length | Hazards | Eligible |
|---|---|---|---|---|---|---|
| `rt-osrm-c01c-00` | 4,300.9 m | 100.0 | 47/47 images | 93.87 % | 0 | **no** |
| `rt-osrm-c01c-01` | 4,995.2 m | 100.0 | 65/65 images | 86.17 % | 0 | **no** |

Observed, expected behaviour:

- Imagery was genuinely fetched from Mapillary (112 images across both routes,
  cached under `data/imagery/mapillary/`), each with real coordinates and
  `distance_to_segment_m` within the 25 m matching radius.
- Every frame was classified **stale**. For this corridor Mapillary coverage is
  from 2026-02-24/25 (258 days before the run) plus older 2019–2021 passes, and
  the policy threshold is `max_age_days: 180`. Limitation text is explicit, e.g.
  *"Imagery is stale (258 days old > 180 days policy threshold); condition may
  not reflect current road state."*
- `comparison.recommendation_status = cannot_determine`, reason
  `no_sufficiently_assessed_route`, `recommended_route_id = null`. Stale evidence
  is never used to justify a recommendation (Rule 9).
- A score of 100 means *"no supported hazard was detected in the available
  imagery"*, not proof of safety; the API states this in `safety_note` and
  `note`.
- Explanation `source: fallback`, ~900 characters of grounded text built only
  from backend data, with disclosures
  `safest_route_cannot_be_determined` and `fewer_than_four_routes_returned`.

### 3.6 Detector sanity (weak model, working pipeline)

To separate "model is weak" from "pipeline is broken", the serving checkpoint
was run on the first 20 images of `data/splits_v2/test.txt` on GPU:

| Confidence | Images with detections | Total detections |
|---|---|---|
| 0.25 (configured) | 1 / 20 | 1 |
| 0.10 | 12 / 20 | 19 |
| 0.05 | 15 / 20 | 41 |

The inference path is functional at the configured 0.25 threshold; the smoke
checkpoint is simply too weak to fire often on street-level imagery. Zero hazards
in the Delhi analysis is therefore consistent with the smoke model plus a
domain gap, not an integration failure.

---

## 4. Substitutions and residual gaps (disclosed)

| # | Item | Status | Impact / handling |
|---|---|---|---|
| 1 | Original `saferoute-yolo11-v1` / `-v2` checkpoints | **Unrecoverable** | Replaced by marked P0 smoke checkpoint; `/api/health` shows `v2` only because the path is canonical. Markers in both directories state this. |
| 2 | Ollama / local LLM | **Not installed** | Accepted for P0. Explanations are deterministic `source: fallback`, fully grounded, no rule weakened. `live_llm` is a config flag, not a liveness probe. |
| 3 | Imagery freshness | **All tested corridors stale** | Mapillary coverage near the tested route is >180 days old. The engine truthfully refuses a recommendation; it does not substitute demo or unrelated imagery. |
| 4 | Public Overpass latency | **Slow (45 s)** | Within the 60 s deadline with mirror failover. Occasional timeouts on `overpass-api.de` were observed; other mirrors answered. |
| 5 | `scripts/evaluate_baseline.py` | Historical hashes | Expects the original v1 SHA-256 `61F6…`. It will not match the smoke substitute — by design; the mismatch is the honest signal that the original artifact is absent. |
| 6 | `scripts/audit/phase24d_evaluate_holdout.py` | Historical hashes | Frozen dataset/split hash constants from the original PHASE_24D run will not match after the portability rewrite. Not run in P0; report rather than silently "fix" the constants (Rule 20). |
| 7 | `data/derived_2class/MANIFEST.json` | Original absolute paths | Retained intentionally as historical provenance; not executable config. |
| 8 | README `mAP ≈ 0.26` vs PHASE_40/41 v2 `mAP50 0.0423` | Pre-existing inconsistency | Out of P0 scope; unresolved and not masked. |

---

## 5. P0 acceptance checklist

| Criterion | Status | Evidence |
|---|---|---|
| Environment restored | ✅ | Python 3.12.10, `.venv`, CUDA available |
| Dependencies installed | ✅ | Pinned versions in §2.1 |
| Configuration validated | ✅ | `load_settings()` + `/api/config`, token redacted |
| Checkpoint verified | ✅ (substitute) | Loads CPU/GPU; `{0: pothole, 1: crack}`; conf 0.25, iou 0.45, imgsz 640 |
| Dataset paths portable | ✅ | Workspace-relative YAML + 3,801 split lines, 0 missing |
| Threshold consistency | ✅ | 0.25 == 0.25; 4/4 tests |
| Tests executed | ✅ | 351 tests OK, 21.791 s |
| App starts | ✅ | Banner + UI 200 + assets 200 |
| Health check passes | ✅ | `status: ok` in ~0.7 s |
| E2E analysis verified | ✅ | Live run `an-16f14c72dbbd`, `partially_assessed`, honest no-recommendation |

---

## 6. Reproduction

From the workspace root (`D:\COde\Major project\Saferoute-AI-Project`):

```powershell
# 1. Environment (already present)
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Config: .env is git-ignored and holds only MAPILLARY_ACCESS_TOKEN

# 3. Smoke checkpoint (only if models/training/p0-smoke is absent)
.\.venv\Scripts\python.exe scripts\p0_smoke_train.py

# 4. Tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v

# 5. Application
.\.venv\Scripts\python.exe scripts\run_app.py --no-browser --port 8000

# 6. Health
curl.exe http://127.0.0.1:8000/api/health
```

---

## 7. Files changed in this work

Modified (20):
`data/dataset.yaml`, `data/dataset_v2.yaml`,
`data/splits/{train,val,test}.txt`, `data/splits_v2/{train,val,test}.txt`,
`scripts/train_baseline.py`, `scripts/evaluate_baseline.py`,
`scripts/verify_yolo_opencv.py`, `scripts/prepare_datayolo_2class.py`,
`scripts/prepare_rdd2022_yolo.py`, `scripts/audit/phase03_dataset_audit.py`,
`scripts/audit/phase20_duplicate_scan.py`,
`scripts/audit/phase20_rdd2022_audit.py`,
`scripts/audit/phase24d_evaluate_holdout.py`,
`tests/integration/test_end_to_end_pipeline.py`, `tests/unit/test_detection.py`,
`tests/unit/test_hazard_aggregation.py`.

Added:
`scripts/p0_smoke_train.py`,
`reports/p0_runnable_environment/P0_RUNNABLE_ENVIRONMENT_REPORT.md` (this file),
`reports/p0_runnable_environment/ENDPOINT_EVIDENCE.json`.

Runtime artifacts (git-ignored, local only):
`models/training/p0-smoke/**`,
`models/training/saferoute-yolo11-{v1,v2}/**`,
`logs/evaluation/qualitative_samples/**`, `data/imagery/mapillary/**`, `.env`,
`.venv`.

---

## 8. Security and data handling

- The Mapillary token was written **only** to the git-ignored `.env`; it was
  never printed in logs or committed.
- A repository-wide scan for the token's unique numeric identifier and secret
  segment returns **zero** matches in tracked files and logs.
- `/api/config` exposes only `mapillary_token_present: true`.
- Downloaded Mapillary frames are cached inside the workspace under
  `data/imagery/` (Rule 1) and remain CC-BY-SA 4.0 with attribution carried in
  each image reference.
- The background API server used for verification was stopped after the run;
  `/api/health` is no longer reachable.

---

## 9. Recommended next steps (post-P0, not part of this run)

1. Restore the genuine accepted v1/v2 checkpoints (if an archive exists) and
   remove the `P0_SMOKE_SUBSTITUTE.json` markers; re-run the model-dependent
   tests and `evaluate_baseline.py` hash checks.
2. Install Ollama + `llama3:latest` if LLM-generated explanations are required;
   verify the explainer reports `source: llm` and stays grounded.
3. Re-run the Delhi analysis against a corridor with imagery captured within the
   180-day freshness window, to exercise a `recommended` (not
   `cannot_determine`) comparison path end to end.
4. Reconcile the README mAP claim with the PHASE_40/41 v2 results, or annotate
   both with their measurement basis.
5. If `phase24d` must be run again, regenerate its frozen hash constants from the
   repaired splits and record the change as a new audited phase outcome rather
   than editing historical values in place.
