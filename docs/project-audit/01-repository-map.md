# 01 — Repository Map

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21 · **Read-only survey**
> **Related:** [`00-executive-summary.md`](00-executive-summary.md) ·
> [`10-code-walkthrough.md`](10-code-walkthrough.md)

---

## 1. Two Git repositories

SafeRoute AI is **not a single repository**. It is a core Python repository with a
**nested, independently-versioned frontend repository** inside it.

| | Core repository | Frontend repository |
|---|---|---|
| Path | `D:\New folder (3)` | `D:\New folder (3)\frontend\Frontend\project frontend` |
| Branch | `main` | `main` |
| HEAD | `53f7f63` — *feat(ui+api): staged route progress, parallel imagery prefetch, latency fixes* | `8449593` |
| Remote | Not inspected | `https://github.com/pshkarsngh/SafeRouteAI.git` |
| Ignore relationship | Outer `.gitignore` ignores `frontend/Frontend/`, so frontend edits **never** appear in the outer `git diff` | — |

**Consequence for reviewers and auditors:** `git status` in the workspace root will *not*
show frontend changes. Any change review, diff review or contribution accounting **must**
be performed in both repositories separately. This is the mechanism behind Finding
**F-07/F-18** in [`14-findings-and-recommendations.md`](14-findings-and-recommendations.md).

## 2. Top-level tree

```
D:\New folder (3)\
├─ master_rules.md                  authoritative root rules (107 lines, 20 rules)
├─ README.md                        project overview + quick start
├─ .env                             local secrets (gitignored — never read into docs)
├─ .env.example                     tracked template of variable NAMES only
├─ .gitignore
├─ requirements.txt                 9 pinned runtime deps + CUDA extra-index-url
├─ requirements-lock.txt            41 fully pinned transitive deps
├─ requirements-dev.txt             header-only (deliberate, Rule 18)
├─ .venv/                           Python 3.12.10 virtual environment
├─ .ultralytics/                    Ultralytics runtime cache
├─ config/                          14 YAML policy files — the runtime source of truth
├─ src/                             backend package (50 modules, 8 590 lines)
├─ tests/                           27 .py files (24 test modules), 5 852 lines, 299 test methods
├─ scripts/                         8 top-level + 10 read-only audit scripts
├─ data/                            datasets, derived datasets, splits, dataset YAMLs
├─ DATA-YOLO/                       upstream dataset (licence unresolved — F-08)
├─ models/                          trained checkpoints + training outputs
├─ weights/                         extra weights
├─ logs/                            evaluation + training provenance records
├─ reports/                         root-level report output directory
├─ runs/                            Ultralytics run directory (currently empty)
├─ frontend/                         deployed static bundle (see §5)
└─ docs/                            64 files: PRD, TRD, ARCHITECTURE, TRAINING_RULES,
                                     evaluation_plan, phases/, reports/, project-audit/
```

## 3. Backend package `src/` — complete module inventory

50 Python files, 8 590 lines. Line counts measured during this audit.

### 3.1 `src/api/` — HTTP layer (4 modules + `__init__`, 1 002 lines)

| File | Lines | Responsibility |
|---|---:|---|
| `src/api/app.py` | 403 | `http.server` API: 10 endpoints, CORS, static SPA serving, path-traversal guard. `SafeRouteAPI`, `_Handler`, `create_server()`, `main()`. |
| `src/api/pipeline.py` | 345 | `SafetyAnalysisPipeline` — orchestration of routing → imagery → preprocessing → detection → aggregation → risk → comparison → explanation. |
| `src/api/bootstrap.py` | 97 | The **only** place live providers are selected from `Settings`. |
| `src/api/store.py` | 144 | `AnalysisStore` — SQLite schema + persistence for analyses, scores, detections, model versions. |

### 3.2 `src/risk/` — deterministic scoring (4 modules, 1 393 lines)

| File | Lines | Responsibility |
|---|---:|---|
| `src/risk/engine.py` | 327 | `DeterministicRiskEngine` — the sole owner of safety scores. `compute_config_hash()`, `S_i = 100·exp(-λ·H_i)`, coverage suppression. |
| `src/risk/comparison.py` | 438 | `RouteComparer.build` — route ranking and the recommendation policy; `assessed_length_fraction()`. |
| `src/risk/aggregate.py` | 310 | `HazardAggregator.assess_segment`, `deduplicate_adjacent_segment_hazards()`, `compute_iou()`. |
| `src/risk/severity.py` | 136 | `SeverityPolicy` — config-driven severity assignment; never LLM-influenced. |
| `src/risk/schemas.py` | 183 | `AssessmentStatus`, `HazardRecord`, `CoverageInfo`, `SegmentAssessment`, `SegmentScoreResult`, `RouteSafetyResult`. |

### 3.3 `src/routing/` — route acquisition (5 modules, 758 lines)

| File | Lines | Responsibility |
|---|---:|---|
| `src/routing/osrm_adapter.py` | 246 | `OSRMRoutingAdapter` — live OSRM client, response cache, bounded retries. |
| `src/routing/mock_adapter.py` | 234 | `MockRoutingAdapter` — synthetic routes, always flagged as demo (Rule 10). |
| `src/routing/segmentation.py` | 222 | `RouteSegmenter`, `haversine_distance_m()`, `compute_linestring_length_m()`. |
| `src/routing/schemas.py` | 141 | `RoutingStatus`, `Coordinate`, `RouteGeometry`, `RouteSegment`, `Route`, `RouteRequest`, `RouteResponse`. |
| `src/routing/adapter.py` | 74 | `load_routing_config()`, `create_routing_adapter()` factory. |
| `src/routing/interfaces.py` | 47 | `RoutingProvider` ABC. |

### 3.4 `src/imagery/` — permitted imagery (5 modules, 897 lines)

| File | Lines | Responsibility |
|---|---:|---|
| `src/imagery/mapillary_provider.py` | 328 | Mapillary Graph API client; token handling, candidate-set fetch, one-time download + workspace cache. |
| `src/imagery/adapter.py` | 300 | `PermittedImageryAdapter` — orchestrates provider + matcher + staleness into `ImageryResult`. |
| `src/imagery/matcher.py` | 117 | `SegmentImageryMatcher` — point-to-segment perpendicular distance within the 25 m buffer. |
| `src/imagery/staleness.py` | 56 | `StalenessEvaluator` — 180-day freshness policy; unknown capture time ⇒ stale. |
| `src/imagery/schemas.py` | 114 | `ImageryStatus`, `ImageRef`, `ImageryUnavailable`, `ImageryResult`. |

### 3.5 `src/facilities/` — context-only facilities (6 modules, 1 402 lines)

| File | Lines | Responsibility |
|---|---:|---|
| `src/facilities/service.py` | 433 | `FacilitiesService` facade + `create_facilities_provider()`; `get_nearby_facilities()`, `get_facilities_near_route()`. |
| `src/facilities/overpass_provider.py` | 430 | Overpass client: per-category queries, 3-mirror failover, 45 s deadline. |
| `src/facilities/schemas.py` | 185 | `Facility`, `FacilityResult` — deliberately contain **no** score/risk field (Rule 11). |
| `src/facilities/geometry.py` | 155 | `distance_to_polylines_m()`, `normalise_polylines()`, `polylines_bbox()`. |
| `src/facilities/mock_provider.py` | 136 | Deterministic offline fixtures. |
| `src/facilities/interfaces.py` | 63 | `FacilitiesProvider` ABC, incl. `get_facilities_in_bbox()`. |

### 3.6 `src/llm/` — grounded explanations (2 modules, 863 lines)

| File | Lines | Responsibility |
|---|---:|---|
| `src/llm/explainer.py` | 818 | `GroundedExplanationService` — `SYSTEM_PROMPT`, schema validation, entity-grounding check, deterministic `_fallback`. |
| `src/llm/schemas.py` | 29 | `ExplanationResult` (`source` ∈ `ollama` \| `fallback`). |

### 3.7 `src/detection/`, `src/preprocessing/`, `src/config/`, `src/geocoding/`

| File | Lines | Responsibility |
|---|---:|---|
| `src/detection/detector.py` | 422 | `HazardDetector.detect()` — YOLO11 inference, `SUPPORTED_CLASSES = {0: pothole, 1: crack}`, bbox rescale, `visualise()`. |
| `src/detection/schemas.py` | 100 | `DetectionStatus`, `DetectionRecord`, `ImageDetectionResult`. |
| `src/preprocessing/pipeline.py` | 459 | `PreprocessingPipeline.validate_image()`, `.letterbox()`, `.preprocess()`, `.prepare_inference_input()`. |
| `src/config/settings.py` | 161 | `Settings` dataclass + `load_settings()`; merges `config/app.yaml` with `.env` overrides. |
| `src/config/env.py` | 118 | `.env` loader, `get_env`/`get_bool`/`get_int`/`get_float`, `WORKSPACE_ROOT`. |
| `src/config/thresholds.py` | 71 | `assert_threshold_consistency()` — the single confidence policy (detector must equal aggregator). |
| `src/geocoding/nominatim.py` | 169 | `NominatimGeocoder` — keyless, ≥1 req/s, bounded retries. |
| `src/geocoding/mock_geocoder.py` | 65 | Offline geocoder fixture. |
| `src/geocoding/factory.py` | 54 | `create_geocoding_provider()`. |
| `src/geocoding/schemas.py` | 68 | `GeocodeStatus`, `GeocodeCandidate`, `GeocodeResult`. |
| `src/geocoding/interfaces.py` | 31 | `GeocodingProvider` ABC. |

## 4. Tests — `tests/` (27 `.py` files; 24 test modules, 5 848 lines, 299 test methods)

| File | Lines | Test methods |
|---|---:|---:|
| `tests/unit/test_facilities_service.py` | 576 | 36 |
| `tests/unit/test_llm_explainer.py` | 452 | 37 |
| `tests/unit/test_route_recommendation_correctness.py` | 474 | 15 |
| `tests/unit/test_multiple_routes_latency.py` | 466 | 13 |
| `tests/unit/test_phase23b_imagery_integrity.py` | 387 | 21 |
| `tests/unit/test_routing_adapter.py` | 297 | 18 |
| `tests/unit/test_risk_engine.py` | 295 | 12 |
| `tests/unit/test_pipeline_parallel_imagery.py` | 289 | 10 |
| `tests/unit/test_hazard_aggregation.py` | 282 | 12 |
| `tests/unit/test_api.py` | 267 | 13 |
| `tests/unit/test_facilities_api.py` | 203 | 12 |
| `tests/unit/test_stale_fresh_regression.py` | 202 | 4 |
| `tests/unit/test_imagery_adapter.py` | 202 | 8 |
| `tests/unit/test_detection.py` | 186 | 9 |
| `tests/unit/test_route_comparison.py` | 181 | 14 |
| `tests/unit/test_preprocessing.py` | 167 | 11 |
| `tests/unit/test_mapillary_provider.py` | 160 | 10 |
| `tests/unit/test_bootstrap_imagery.py` | 137 | 6 |
| `tests/unit/test_geocoding.py` | 74 | 6 |
| `tests/unit/test_detection_outcome.py` | 71 | 6 |
| `tests/unit/test_threshold_consistency.py` | 53 | 4 |
| `tests/unit/test_settings_env.py` | 42 | 2 |
| `tests/integration/test_end_to_end_api.py` | 205 | 16 |
| `tests/integration/test_end_to_end_pipeline.py` | 180 | 4 |
| `tests/{,unit/,integration/}__init__.py` | 4 | 0 |

**No `pytest` is installed.** The suite is written for `unittest` and must be run with
`python -m unittest discover -s tests`. `requirements-dev.txt` is deliberately
header-only (Rule 18).

## 5. `frontend/` — two distinct things

The `frontend/` directory at the workspace root contains **two different things**, and
conflating them is a recurring source of confusion:

| Path | What it is | Tracked by |
|---|---|---|
| `frontend/index.html`, `frontend/assets/` | A **prebuilt static bundle** served by the backend (`_Handler.static_dir` = `WORKSPACE_ROOT / "frontend"`). Contains `index-ChLfkaQi.js`, `index-sD57dfm8.css`, `maplibre-gl-shared.mjs`, `maplibre-gl-worker.mjs` and 10 lottie chunks. | Core repo |
| `frontend/Frontend/project frontend/` | The **frontend source repository** — 89 files under `src/`, its own `package.json`, `dist/`, `tools/`. | Nested repo (outer `.gitignore` excludes it) |

The nested repo's own build output (`dist/assets/index-BCNmOTIq.js`) has **different
content hashes** from the outer bundle (`index-ChLfkaQi.js`), proving they are different
builds. See Finding **F-06**.

## 6. Frontend source layout — `frontend/Frontend/project frontend/src/` (89 files)

| Area | Path | Notes |
|---|---|---|
| Entry | `main.tsx`, `App.tsx`, `index.css` | Router mounted in `App.tsx` via `BrowserRouter`. |
| Pages | `src/pages/` | `Home`, `Search`, `RouteResults`, `Projects`, `About`, `Services`, `Contact`, `NotFound`. |
| Components | `src/components/` | Map panel, route cards, hazard panels, facility layer, animations. |
| Hooks | `src/hooks/useSafeRoute.ts` | The main analysis orchestration hook. |
| API | `src/lib/api.ts` | The **only** `fetch` module in the frontend. |
| Services | `src/services/facilities.ts` | Maps backend facility records to UI shape. |
| Utils | `src/utils/facilityPresentation.ts` | Centralises facilities wording (Phase 2). |
| Utils | `src/utils/safety.ts` | **Dead code** — see F-07. |
| Utils | `src/utils/backendRoutes.ts` | Normalises backend route payloads for the map. |
| Assets | `src/assets/` | Includes the unreferenced `indroute-logo.svg`. |
| Tests | `tools/frontend-tests/`, `tools/browser-test/` | Outside `src/`. |

## 7. Configuration — `config/` (14 YAML files)

These are the **runtime source of truth** for every threshold and policy. A behaviour
change should be a config change, not a code change.

| File | Purpose |
|---|---|
| `app.yaml` | Runtime provider selection **and** the server/LLM/imagery settings: `app.routing_provider`, `app.facilities_provider`, `app.imagery_source`, `app.geocoding.*`, `app.imagery.*` (including `demo_mode: false`), `app.llm.*` (Ollama URL, `llama3:latest`, 45 s timeout), `app.server.{host,port}`, `app.user_agent`, `app.static_dir`. |
| `detection.yaml` | Inference settings, checkpoint path, supported/unsupported classes. |
| `hazard_severity.yaml` | Confidence threshold, IoU dedup, base severities, modulation, status rules. |
| `risk_engine.yaml` | λ, score bounds, segment normalisation, coverage policy, config hash source. |
| `routing.yaml` | OSRM endpoint, timeouts, retries, segmentation policy, Rule-10 guardrail. |
| `route_comparison.yaml` | The recommendation policy (`policy_version: comparison-v1`) — minimum assessed-length fraction, refusal conditions. |
| `imagery.yaml` | Permitted source registry, 25 m matcher radius, 180-day staleness, demo guard. |
| `facilities.yaml` | Overpass mirrors, per-category OSM tags, search bounds, road-access caps. |
| `geocoding.yaml` | Nominatim base URL, country bias, request pacing. |
| `preprocessing.yaml` | `pipeline_version: preprocess-v1`; validation thresholds (min width/height/channels, supported extensions). |
| `training_baseline.yaml` | Frozen v1 baseline hyperparameters (`saferoute-yolo11-v1`, PHASE_07). |
| `training_improved.yaml` | v2 hyperparameters (`saferoute-yolo11-v2`, TRAIN-V2) — stronger augmentation, longer schedule, cosine LR. |
| `training_canonical.yaml` | The single documented canonical training workflow (see the class-2 caveat in [`04-dataset-and-labeling.md`](04-dataset-and-labeling.md) §5.5). |
| `training_datayolo.yaml` | The DATA-YOLO experimental training configuration (`saferoute-yolo11-datayolo-exp`). |

**Note.** There is **no** `config/llm.yaml`, `config/api.yaml`, `config/app_settings.yaml`,
`config/training.yaml`, `config/dataset.yaml` or `config/evaluation.yaml`. The LLM,
server and imagery settings live inside `config/app.yaml`; the dataset YAMLs live in
`data/` (`data/dataset.yaml`, `data/dataset_v2.yaml`, `data/datayolo_prep/dataset.yaml`).
This corrects an earlier draft of this map.

`src/config/thresholds.py::assert_threshold_consistency()` cross-checks
`detection.yaml → inference.conf` against `hazard_severity.yaml →
thresholds.confidence_threshold` and **raises** if they diverge — the fix for a real
historical defect where the detector ran at 0.15 and the aggregator at 0.25, silently
discarding every detection in between.

## 8. Data, models, logs

### 8.1 `data/`

| Path | Contents (measured) |
|---|---|
| `data/datayolo_prep/` | 1 789 images (train 1 251 / val 269 / test 269), 2 535 label rows (class 0 = 1 505, class 1 = 1 030), 0 empty labels. `MANIFEST.json` records `images_total: 2736`, `eligible: 1789`, 644 groups, and 947 exclusions. |
| `data/derived_2class/` | 2 009 images on disk, 1 792 of them labelled; 3 420 label rows, 336 empty labels. |
| `data/splits_v2/` | train 1 398 / val 178 / test 216 / quarantined 212. Date-atomic split (train 2025-02-18/19; val 2025-02-16, 2025-02-23, 2025-03-16; test 2025-02-26). |
| `data/dataset.yaml` | Serving dataset **v1** — splits train 1 406 / val 402 / test 201. |
| `data/dataset_v2.yaml` | Serving dataset **v2** — points at `data/derived_2class`. |
| `data/pothole_crack_manhole/data/README.md` | Carries a Zenodo DOI `10.5281/zenodo.17834373`. |

### 8.2 `models/`

| Path | Contents |
|---|---|
| `models/training/saferoute-yolo11-v1/` | 49 epochs. `best.pt` SHA-256 `61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65`. |
| `models/training/saferoute-yolo11-v2/` | 144 rows in `results.csv`, early stop at epoch 104. `best.pt` SHA-256 `B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA` — **the serving checkpoint** per `config/detection.yaml`. |
| `models/training/saferoute-yolo11-datayolo-exp/` | 68 epochs. `best.pt` SHA-256 `730CE43974AF67BB228704C981D55D0FF8879FC42A4C75DF646ABE289FD590BB`. |
| `yolo11n.pt` (root) | 5 613 764 B — base pretrained weights. |
| `weights/yolo26n.pt` | 5 544 453 B — additional weights. |
| `runs/detect/` | Empty. |

### 8.3 `logs/`

| Path | Contents |
|---|---|
| `logs/evaluation/evaluation_record.json` | Repo-reported v1 metrics + decision. Contains the internal inconsistency F-03. |
| `logs/training/saferoute-yolo11-datayolo-exp/` | `run_record.json` (stale — F-04), `train.log`, `results.csv`. |

### 8.4 `DATA-YOLO/`

Upstream source dataset. **No licence file exists anywhere** (F-08). `Road_crack/README.md`
is 0 bytes. `DATA-YOLO/Pushkar Singh Baghel.pdf` is a personal résumé.

## 9. Scripts

### 9.1 Top level (`scripts/`, 8 files)

| Script | Lines | Purpose |
|---|---:|---|
| `prepare_datayolo_2class.py` | 603 | Builds `data/datayolo_prep` (2-class, group-aware, leakage-aware). |
| `build_derived_dataset_v2.py` | 452 | Builds `data/derived_2class` + `data/splits_v2` (date-atomic). |
| `train_baseline.py` | 360 | YOLO11 training wrapper with recorded args. |
| `evaluate_baseline.py` | 319 | Evaluation → `logs/evaluation/evaluation_record.json`. |
| `verify_yolo_opencv.py` | 274 | Sanity-checks the YOLO + OpenCV pair. |
| `prepare_rdd2022_yolo.py` | 123 | **CLI not implemented** (F-05). |
| `measure_flow.py` | 59 | `python scripts/measure_flow.py <port> <routes_body.json> <analyze_body.json>`. |
| `run_app.py` | 58 | `--host/--port/--no-browser`; single-command API + UI launch. |
| `run_app.ps1` | 26 | PowerShell wrapper. |

### 9.2 `scripts/audit/` (10 files)

All read-only; they write **only** under `reports/`. Used for dataset audits, leakage
scans, confidence sweeps and submission preparation.

## 10. `docs/` — 64 files

| Location | Count | Contents |
|---|---:|---|
| `docs/` root | 5 | `ARCHITECTURE.md` (23 787 B), `PRD.md` (16 407 B), `TRD.md` (27 732 B), `TRAINING_RULES.md` (14 369 B), `evaluation_plan.md` (2 772 B). |
| `docs/phases/` | 20 | Per-phase implementation reports. |
| `docs/reports/` | 38 | Per-phase verification reports, incl. `PHASE_28_LLM_EXPLANATION_REPAIR.md`, `PHASE_29_HOSPITAL_ACCESSIBILITY.md`, `DATA_YOLO_TRAINING_PREP.md`. |
| `docs/project-audit/` | 16 (+ this set) | This audit. |

**Not found:** no `PHASE_21`, `PHASE_26`, `PHASE_27` or `PHASE_30` report exists, even
though the phase identifiers appear in commit messages and in-code comments. The numbering
is non-contiguous; this is recorded as an observation, not a defect.

## 11. What is **not** in this repository

| Expected | Status |
|---|---|
| `.github/` workflows | **Not found** |
| `Dockerfile` / `docker-compose.yml` for the core repo | **Not found** (a separate sub-project `frontend/Frontend/project frontend/SafeRouteAI/` has one) |
| `Makefile`, `tox.ini`, `noxfile.py`, `pyproject.toml`, `setup.py` | **Not found** |
| `.pre-commit-config.yaml`, `CODEOWNERS` | **Not found** |
| Database migrations (`alembic/`, `migrations/`) | **Not found** — schema is created idempotently by `AnalysisStore._init_schema()` |
| `pytest.ini` / `pytest` dependency | **Not found** — deliberate (Rule 18) |
| ESLint / Prettier config in the frontend | **Not found** — `oxlint` is used instead |
| Frontend test framework (Jest / Vitest / Playwright) | **Not found** — hand-rolled harnesses |
| `LICENSE` for the SafeRoute AI code itself | **Not found** |
| Licence for `DATA-YOLO/` | **Not found** (F-08) |

---

*All counts in this document were measured during the 2026-10-21 read-only audit. Paths
are workspace-relative unless prefixed with an absolute path.*
