# 10 — Code Walkthrough

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Related:** [`01-repository-map.md`](01-repository-map.md) ·
> [`02-architecture-and-data-flow.md`](02-architecture-and-data-flow.md)

This is a guided tour of the codebase, ordered by responsibility. Every file path and
function name below was read from the source and exists at the path shown.

---

## 1. Where to start reading

If you have 15 minutes, read in this order:

| # | File | Why |
|---:|---|---|
| 1 | `master_rules.md` | The 20 rules every implementation decision answers to. |
| 2 | `src/api/pipeline.py` | The whole system in 345 lines: orchestration order made explicit. |
| 3 | `src/risk/engine.py` | The scoring formula and the coverage policy. |
| 4 | `src/risk/comparison.py` | When the system refuses to recommend a route. |
| 5 | `src/llm/explainer.py` (header + `SYSTEM_PROMPT`) | The LLM boundary. |
| 6 | `src/facilities/service.py` | A complete, small, self-contained feature — good template for a walkthrough. |
| 7 | `src/api/app.py` | The HTTP surface. |

## 2. Backend tour

### 2.1 `src/api/pipeline.py` — `SafetyAnalysisPipeline` (345 lines)

The orchestration spine. Its import list is itself a summary of the architecture:
`src.config.thresholds`, `src.facilities.service`, `src.imagery.adapter`,
`src.llm.explainer`, `src.risk.aggregate`, `src.risk.comparison`, `src.risk.engine`,
`src.risk.schemas`, `src.routing.adapter`.

Its docstring states the invariants:

> All structured calculations happen here/backend-side. The risk engine owns scores
> (Rule 7); facilities never enter the score (Rule 11); the LLM only explains (Rule 12).

**Key behaviours to look for:**

- **Imagery prefetch is parallel.** A `ThreadPoolExecutor` fetches imagery for segments
  concurrently. `tests/unit/test_pipeline_parallel_imagery.py` (10 methods) and
  `tests/unit/test_multiple_routes_latency.py` (13 methods) guard this.
- **Failure is absorbed, not propagated.** A segment whose imagery failed becomes an
  unassessed segment and the pipeline continues.
- **`assert_threshold_consistency()` is called at analysis time**, so a config drift
  between the detector and the aggregator fails the run loudly instead of silently
  discarding detections.

### 2.2 `src/risk/engine.py` — `DeterministicRiskEngine` (327 lines)

Engine version `risk-v1`. The class docstring lists the hard constraints: sole owner of
safety scores; deterministic; independent of the LLM; facilities excluded; unassessed
never scored as safe.

| Function / member | Role |
|---|---|
| `compute_config_hash(config_path)` | SHA-256 over the risk-engine YAML, uppercased. Stored on every result. |
| `DeterministicRiskEngine.assess_segment(...)` | Segment-level hazard density and score. |
| `DeterministicRiskEngine.score_route(...)` | Route-level aggregation and coverage. |
| Coverage suppression | `is_suppressed` flag + `segment_score = None` when coverage < `min_coverage_threshold`. |

The single most instructive line in the project is the config value
`unassessed_score_placeholder: null` in `config/risk_engine.yaml`. It is not `100.0`.
That is Rule 9 expressed as data.

### 2.3 `src/risk/comparison.py` — `RouteComparer` (438 lines)

Pure function over already-computed scores. Its docstring enumerates the invariants:
never computes a score; never ranks an unassessed route; excludes demo-imagery routes;
requires a minimum assessed-length fraction; **ties produce no recommendation**;
identical inputs produce identical output.

`assessed_length_fraction()` is the function that decides defensibility — it measures
the fraction of a route's *length* that carries a score, not the fraction of its
segments. Length-weighting is the difference between "most segments had images" and
"most of the road was looked at".

### 2.4 `src/risk/aggregate.py` — `HazardAggregator` (310 lines)

| Function | Role |
|---|---|
| `compute_iou(box1, box2)` | Standard IoU over `[x1, y1, x2, y2]`. |
| `deduplicate_adjacent_segment_hazards(...)` | Removes the same physical hazard counted on both sides of a segment boundary (IoU 0.50 per config). |
| `HazardAggregator.assess_segment(...)` | Applies threshold → severity → dedup, then derives the segment status. |

### 2.5 `src/risk/severity.py` — `SeverityPolicy` (136 lines)

Pure, config-driven. `severity = clamp(base × area_factor × conf_factor, min, max)`.
Every value is reconstructible from `config/hazard_severity.yaml` plus the detection
attributes — which is exactly the TRD §8.2 requirement.

### 2.6 `src/detection/detector.py` — `HazardDetector` (422 lines)

Module version `detect-v2`, `MODEL_VERSION = "saferoute-yolo11-v2"`.

| Item | Value |
|---|---|
| `SUPPORTED_CLASSES` | `{0: "pothole", 1: "crack"}` |
| Default checkpoint | `models/training/saferoute-yolo11-v2/weights/best.pt` |
| Inference | `imgsz 640`, `conf 0.25`, `iou 0.45`, `max_det 300`, `augment false`, `batch 1` |

Look for the bbox rescaling: detections are returned in both original-pixel
(`bbox_xyxy`) and normalised (`bbox_norm`) form, and the rescale uses the letterbox
parameters from the preprocessing stage rather than an assumed image size.

`visualise()` writes to a copy. It never writes over a source image.

### 2.7 `src/preprocessing/pipeline.py` — `PreprocessingPipeline` (459 lines)

`__version__ = "preprocess-v1"`. The module-level docstring says "Versioned,
deterministic OpenCV validation, letterbox resizing, inference preparation, and
non-destructive visualisation."

| Method | Role |
|---|---|
| `validate_image(path)` | The seven-way status check (§5 of the preprocessing doc). |
| `letterbox(image, size)` | Aspect-preserving pad to the inference size. |
| `preprocess(image)` | The composed deterministic transform. |
| `prepare_inference_input(...)` | Produces the array handed to the detector, plus the metadata needed to rescale boxes back. |

### 2.8 `src/llm/explainer.py` — `GroundedExplanationService` (818 lines)

The largest module, and the one that most deserves a careful read because it holds the
project's hardest boundary.

| Element | Role |
|---|---|
| `SYSTEM_PROMPT` | States the output contract and the prohibition on introducing new facts. |
| Grounded payload builder | Sends only verified results, with a **bounded representative sample** of hazards plus exact totals. |
| Schema validation | Rejects a reply that does not match the contract. |
| Entity-grounding check | Rejects a reply that references a route or hazard not present in the input. |
| `_fallback()` | Deterministic template built only from verified data; sets `source: "fallback"`. |

The Phase-28 docstring at the top of the file is a good piece of engineering writing: it
explains the original failure, its cause (a ~140 KB prompt causing the local model to
continue the data as JSON), and the fix. Read it before changing anything here.

### 2.9 `src/facilities/` — the Phase 2 consolidation (6 modules, 1 402 lines)

The most self-contained feature in the codebase, and the best template for a
walkthrough or a code-quality discussion.

| Module | Role |
|---|---|
| `interfaces.py` | `FacilitiesProvider` ABC, including `get_facilities_in_bbox(bbox=(south, west, north, east), categories)`. |
| `schemas.py` | `Facility` and `FacilityResult`. **No score, risk or hazard field exists in this module** — that is Rule 11 enforced at the type level. |
| `geometry.py` | `normalise_polylines()`, `polylines_bbox()`, `distance_to_polylines_m()` — straight-line distance from a facility to the route corridor. |
| `overpass_provider.py` | Per-category Overpass queries, 3-mirror failover, 0.7 s gap, 45 s deadline. |
| `mock_provider.py` | Deterministic offline fixtures. |
| `service.py` | `FacilitiesService` facade; `get_nearby_facilities()` (circle) and `get_facilities_near_route()` (corridor); `create_facilities_provider()`. |

The `distance_kind` field on a facility is the honesty device: it distinguishes a
straight-line distance from a road-network distance, so a consumer can never mistake one
for the other.

### 2.10 `src/imagery/` — permitted imagery (5 modules, 897 lines)

| Module | Role |
|---|---|
| `mapillary_provider.py` | Graph API client; token handling; candidate-set fetch; one-time download into the workspace cache. |
| `adapter.py` | `PermittedImageryAdapter` — composes provider + matcher + staleness into an `ImageryResult`. |
| `matcher.py` | `SegmentImageryMatcher` — perpendicular point-to-segment distance using a local equirectangular projection centred on the segment's first vertex, clamped to the segment extent. |
| `staleness.py` | `StalenessEvaluator` — 180 days; **unknown capture time ⇒ stale**. |
| `schemas.py` | `ImageRef` (with `is_demo` and `is_stale` flags), `ImageryUnavailable`, `ImageryResult`. |

`matcher.py` is worth reading carefully: the local planar projection is a deliberate
approximation, valid at the scale of a single segment, and the docstring says so.

### 2.11 `src/routing/` (5 modules, 758 lines)

`OSRMRoutingAdapter` (246 lines) is a clean example of a bounded external client:
5 s timeout, 3 retries, 0.5 s backoff, 120 s response cache, and a typed
`RouteResponse` that carries `status`, `limitations` and `error_message`.

`segmentation.py` provides `haversine_distance_m()` and
`compute_linstring_length_m()` — both used by the imagery matcher and the risk engine.

### 2.12 `src/config/` — the settings layer (3 modules, 350 lines)

| Module | Role |
|---|---|
| `env.py` | `.env` loading and typed accessors. `WORKSPACE_ROOT` anchors every path. |
| `settings.py` | `Settings` dataclass merging `config/app.yaml` with `.env` overrides; `to_safe_dict()` for the non-secret `/api/config` view. |
| `thresholds.py` | `assert_threshold_consistency()` — the single-confidence-policy guard. |

### 2.13 `src/api/store.py` — `AnalysisStore` (144 lines)

The `_SCHEMA` string is the entire database definition — five `CREATE TABLE IF NOT
EXISTS` statements. `save_analysis()` writes with `INSERT OR REPLACE` for idempotency,
and explicitly deletes prior `hazard_detections` for the analysis before re-inserting.

### 2.14 `src/api/app.py` — `SafeRouteAPI` and `_Handler` (403 lines)

| Method | Role |
|---|---|
| `SafeRouteAPI.health()` / `.config()` | Liveness and the non-secret capability summary. |
| `SafeRouteAPI.routes()` / `.analyze()` / `.geocode()` | POST handlers. |
| `SafeRouteAPI.get_analysis()` / `.hazards()` / `.comparison()` / `.explanation()` | Read-only projections of the stored record. |
| `SafeRouteAPI.facilities()` | The Phase-2 endpoint; handles both the point and the corridor shape. |
| `_resolve_location()` | Accepts coordinates or a place name. |
| `_Handler.do_GET` / `.do_POST` / `.do_OPTIONS` | Dispatch. |
| `_Handler._serve_static` / `._serve_spa_index` | Static serving with path-containment checks. |
| `_Handler.log_message` | Overridden to a no-op — quiet and secret-free logs. |

## 3. Frontend tour

### 3.1 Entry and routing

| File | Role |
|---|---|
| `src/main.tsx` | React entry point. |
| `src/App.tsx` | `BrowserRouter` + route table. |
| `src/index.css` | Global styles, Tailwind entry. |

**Routes:** `/` (Home), `/search` (Search), `/route-results` (RouteResults), `/projects`,
`/about`, `/services`, `/contact`, and `*` (NotFound).

### 3.2 `src/lib/api.ts` — the only network module

Every backend call in the frontend goes through this file. It is the single place that
reads `VITE_API_URL`, `VITE_YOLO_URL`, `VITE_ANALYZE_TIMEOUT_MS` and `VITE_OSRM_URL`.

| Export | Role |
|---|---|
| `ApiError` | Typed error with kinds `network`, `timeout`, `http`, `invalid`, `aborted`. |
| Route request helpers | `POST /api/routes`, `GET /api/health` |
| Analysis helpers | `POST /api/analyze`, `GET /api/analyze/{id}` |
| Sub-resource helpers | `/api/analysis/{id}/hazards`, `/comparison`, `/explanation` |
| Facilities helper | `POST /api/facilities` |

The timeouts (analyze 900 000 ms, routes 60 000 ms, facilities 90 000 ms) live here,
which is why a slow analysis does not time out prematurely.

**Note.** `VITE_OSRM_URL` and `VITE_YOLO_URL` remain in the environment surface, but
after the Phase 2 consolidation the browser does not call Overpass; the OSRM variable
is likewise not used for a direct browser-to-OSRM call on any live path.

### 3.3 `src/hooks/useSafeRoute.ts` — the orchestration hook

Holds the analysis state machine: idle → routing → analysing → results, with the
loading and error states the UI needs. It calls `src/lib/api.ts` and normalises the
payloads via `src/utils/backendRoutes.ts`.

### 3.4 `src/pages/RouteResults.tsx` — the results page

The main presentation surface. It contains:

- `MedicalAccessSection` — the facilities panel, with `data-testid="medical-access"` and
  a `facility-warning` element.
- The route comparison, score and coverage display.
- The hazard evidence list.

**Design observation.** Hazards are listed as text with their classes and confidences;
they are **not** drawn as markers on the map, and the map uses no MapLibre `Popup`.
This is a presentational gap rather than a defect — the evidence is shown, just not
spatially.

### 3.5 `src/utils/facilityPresentation.ts` — centralised wording

Phase 2 introduced this module to centralise the facilities wording and the
`medical` → `medicalFacility` category mapping, so the label logic exists in exactly one
place.

### 3.6 `src/services/facilities.ts` — mapping layer

Translates the backend `Facility` / `FacilityResult` records into the UI shape the
components consume.

### 3.7 `src/utils/backendRoutes.ts` — route normalisation

Normalises the backend route payloads into the geometry shape the MapLibre layer
expects.

### 3.8 Dead code in the frontend — read before editing

| File | Lines | Status |
|---|---:|---|
| `src/utils/safety.ts` | 317 | **Dead.** Contains `analyzeRoutes` — an independent route-scoring implementation. **Not imported anywhere.** Finding F-07. |
| `src/services/routing.ts` | 171 | **Dead.** `fetchRoadRoutes` — superseded by the backend. |
| `src/components/Header/**` | 8 files | **Dead.** |
| `src/components/common/Stairs.tsx` | — | **Dead.** |
| `src/components/ui/animated-search-1.tsx` | 416 | **Dead.** Also the only `clsx` consumer. |
| `src/assets/indroute-logo.svg` | — | **Dead.** |
| `public/assets/maplibre-gl-*.mjs` | — | **Dead.** Worker copies superseded by the bundled build. |

`src/utils/safety.ts` deserves special attention. It is the only place in the frontend
where a safety score appears to be computed, and it contradicts the "backend is the only
score authority" rule. A reviewer who finds it by accident may reasonably conclude the
project has two scoring implementations. It has one.

### 3.9 Frontend test harnesses

| File | What it does |
|---|---|
| `tools/frontend-tests/run.mjs` | The runner. 49 static `check()` sites → 58 runtime checks. |
| `tools/frontend-tests/entry.ts` | The check definitions, bundled by Vite before execution. |
| `tools/browser-test/run.mjs` | Edge + CDP driver. 15 static checks → 11–15 runtime. |

## 4. Scripts tour

| Script | Use it when |
|---|---|
| `scripts/run_app.py` | Starting the system. |
| `scripts/run_app.ps1` | The same, from PowerShell. |
| `scripts/prepare_datayolo_2class.py` | Rebuilding `data/datayolo_prep` from `DATA-YOLO/`. |
| `scripts/build_derived_dataset_v2.py` | Rebuilding `data/derived_2class` and `data/splits_v2`. |
| `scripts/train_baseline.py` | Training a YOLO11 baseline. |
| `scripts/evaluate_baseline.py` | Producing `logs/evaluation/evaluation_record.json`. |
| `scripts/verify_yolo_opencv.py` | Sanity-checking the YOLO + OpenCV pair before a long run. |
| `scripts/measure_flow.py` | Measuring end-to-end latency. Usage: `python scripts/measure_flow.py <port> <routes_body.json> <analyze_body.json>` |
| `scripts/prepare_rdd2022_yolo.py` | **Broken — CLI not implemented (F-05).** |
| `scripts/audit/*.py` | Read-only audits. They write **only** under `reports/`. |

## 5. Reading paths by interest

| If you want to understand… | Read |
|---|---|
| How a number becomes a score | `config/risk_engine.yaml` → `src/risk/severity.py` → `src/risk/aggregate.py` → `src/risk/engine.py` → `src/risk/comparison.py` |
| How honesty is enforced | `config/imagery.yaml` → `src/imagery/staleness.py` → `src/risk/engine.py` (coverage suppression) → `src/risk/comparison.py` (refusal) |
| How the LLM is kept in bounds | `src/llm/explainer.py` (`SYSTEM_PROMPT`, grounding, `_fallback`) → `tests/unit/test_llm_explainer.py` |
| How a provider failure is handled | `src/routing/osrm_adapter.py` → `src/imagery/mapillary_provider.py` → `src/facilities/overpass_provider.py` → `src/api/pipeline.py` |
| How facilities stay out of the score | `src/facilities/schemas.py` (no score field) + `config/facilities.yaml` `guardrails` + the import graph in [`02-architecture-and-data-flow.md`](02-architecture-and-data-flow.md) §3 |
| How the UI is wired | `src/lib/api.ts` → `src/hooks/useSafeRoute.ts` → `src/utils/backendRoutes.ts` → `src/pages/RouteResults.tsx` |
| How the project is tested | `tests/unit/test_route_recommendation_correctness.py` (policy) and `tests/unit/test_phase23b_imagery_integrity.py` (integrity) are the two most informative test files |

---

*Every path and symbol named in this document was verified against the source tree on
2026-10-21.*
