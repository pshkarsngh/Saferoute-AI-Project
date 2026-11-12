# SafeRoute AI — Independent Project Health, Functionality & Release-Readiness Audit

**Audit date:** 2026-11-10
**Repository:** `D:\COde\Major project\Saferoute-AI-Project`
**Git HEAD:** `b3ee84fc2f2de50eb1fdba6d48d8729179ed49f0` (branch `main`, working tree dirty with uncommitted Phase 42/43 work)
**Auditor role:** independent senior architect / QA lead / ML engineer / security reviewer
**Scope:** read-only inspection and execution. No production code, config, model weights, datasets, risk formulas, checkpoints, or user data were modified. No installs, downloads, training, commits, or pushes were performed. The only artifact created is this report.
**Governing document:** `master_rules.md` (107 lines) was read in full before testing.

**Evidence key**

| Label | Meaning |
|---|---|
| **VERIFIED** | Directly executed during this audit and observed. |
| **CODE-VERIFIED** | Inspected in implementation; not executed in this audit. |
| **REPORTED** | Documented by earlier phase reports; not independently reproduced. |
| **NOT TESTED** | Not exercised in this audit. |
| **BLOCKED** | Cannot be tested because a required asset/dependency/permission is missing. |

---

## 1. Executive Summary

SafeRoute AI is a **real, working end-to-end prototype** with unusually strong evidence-honesty engineering. During this audit the system:

- started from the documented launcher,
- returned **4 genuine, geometrically valid routes** from live OSRM **and** Valhalla,
- geocoded live places through Nominatim,
- retrieved live Overpass facilities,
- ran the full YOLO11 → hazard aggregation → `DeterministicRiskEngine` → comparison → explanation pipeline in **~58 s** via API and **~140 s** through the browser,
- correctly **refused to name a safest route** because all evidence was stale,
- displayed only routes the providers actually returned,
- passed the **entire existing test suite: 459 tests, OK, 76.370 s, 0 failures/skips/errors**.

However, the audit also found **release-blocking integrity defects**:

1. **The canonical `saferoute-yolo11-v2` serving checkpoint is byte-identical to the P0 smoke model** (`SHA-256 19619F99…B916D0`), yet `/api/health`, `/api/config`, analysis records, and the UI all present it as `saferoute-yolo11-v2`. A marker file (`P0_SMOKE_SUBSTITUTE.json`) explicitly says *“NOT the original saferoute-yolo11-v2 artifact … Do not use for safety claims or production evaluation.”* This directly violates a required project rule.
2. **No genuine v2 checkpoint exists**; independent detector evaluation is `NOT_ASSESSED`; `data/independent/` does not exist; 0 approved independent sources; dataset freeze refused; reference registry is proxy-only.
3. **The frontend cannot follow configuration**: the built bundle hardcodes `http://localhost:8000`, so running the documented `--port` flag produces an honest but total UI failure.
4. **The shipped UI is a different product shell** (“INDROUTE / THE WORLD IS A BOOK”) and its origin/destination search is a **hardcoded ~23-city list**, not live geocoding.
5. **Invalid coordinates are silently replaced** by a hardcoded Bengaluru default instead of returning HTTP 400.
6. **Documentation is stale/contradictory**: PRD/TRD/ARCHITECTURE still describe the system as not implemented, and README’s `mAP@0.5 ≈ 0.26` conflicts with Phase 40’s reported `0.0423`.

**Bottom line:** the architecture and safety logic are genuinely good, but the project is **not release-ready** and currently **misrepresents its detector identity**. It should be classified as an **ADVANCED PROTOTYPE**, not a release candidate.

---

## 2. Overall Project Status

| Dimension | Status | Evidence |
|---|---|---|
| Application boots | **PASS** | `scripts/run_app.py --no-browser --port 8000` → `/api/health` HTTP 200 (VERIFIED) |
| Live routing | **PASS** | 4 routes from OSRM + Valhalla, valid geometry (VERIFIED) |
| Live geocoding | **PASS** | Nominatim resolved “Bengaluru”; gibberish → `no_results` (VERIFIED) |
| Live facilities | **PASS** | Overpass returned 29 records with OSM attribution (VERIFIED) |
| Detection pipeline executes | **PASS (functionality only)** | 27/39 images processed, hazards aggregated (VERIFIED) |
| Genuine v2 model present | **FAIL** | Canonical checkpoint = smoke substitute (VERIFIED) |
| Independent model evaluation | **BLOCKED** | Prerequisites absent; Phase 42 `NOT_ASSESSED` (VERIFIED) |
| Deterministic risk engine | **PASS** | Sole scorer; stale evidence suppresses recommendation (VERIFIED) |
| Frontend end-to-end | **PARTIAL PASS** | Full flow works only on port 8000; static city list (VERIFIED) |
| Automated tests | **PASS** | 459/459 OK (VERIFIED) |
| Documentation accuracy | **FAIL** | Stale PRD/TRD/ARCHITECTURE; README metric conflict (VERIFIED) |
| Security posture | **PARTIAL** | Traversal guard + token redaction good; no auth/rate limit/TLS (VERIFIED/CODE-VERIFIED) |

**Overall:** functional prototype with advanced backend/safety engineering, blocked from release by model-identity misrepresentation and absent independent validation.

---

## 3. Engineering Implementation Completeness

### Score A — Engineering implementation completeness: **67 / 100**

| Category | Weight | Category score | Weighted | Why |
|---|---:|---:|---:|---|
| Backend and architecture | 15 | 88% | 13.20 | Layered stdlib HTTP server, pipeline, store, provider factories, schemas, typed config all exist and run. Deductions for hardcoded `MODEL_VERSION`, hardcoded default origin, duplicate/mock paths, stale docs. |
| Frontend and user experience | 15 | 55% | 8.25 | MapLibre UI, controls, inputs, results, hazards, facilities and honest states all work. But static 23-city list, hardcoded API base, unrelated landing brand, no configurable backend. |
| Routing and integrations | 10 | 85% | 8.50 | Two live providers composed/de-duplicated with real geometry; timeouts/retries; Nominatim/Overpass/Mapillary/Ollama factories. Public demo endpoints and untested adversarial failure paths. |
| Hazard detection pipeline | 10 | 50% | 5.00 | Complete preprocessing/detector/aggregation/schema code and consistent thresholds. But the served checkpoint is a smoke substitute labelled v2; no genuine artifact. |
| Deterministic risk and safety | 15 | 88% | 13.20 | Single engine owns scoring; coverage, stale, tie and eligibility rules implemented and exercised. Deductions for invalid-coordinate defaulting and stale severity model metadata. |
| LLM grounding | 5 | 75% | 3.75 | Grounding validator, entity/score checks and deterministic fallback exist. Live Ollama-grounded prose was not verified; observed runs used fallback. |
| Dataset and evaluation | 10 | 15% | 1.50 | Governance tooling delivered, but no independent dataset, no freeze, no approved source, no evaluation. |
| Testing and reliability | 10 | 78% | 7.80 | 459 hermetic tests pass. No genuine-model evaluation, no browser test in suite, no load/soak or external-failure injection. |
| Security and deployment | 10 | 55% | 5.50 | Path-traversal guard, secret redaction, timeouts, bounded retries. No auth, rate limiting, TLS, container/deploy manifest; CORS `*`. |
| **Total** | **100** | — | **66.70 ≈ 67** | |

**Interpretation:** as *source code and architecture*, this is a mature prototype. The missing 33 points are concentrated in the model asset, frontend wiring, independent data, and production hardening — not in basic feature existence.

---

## 4. Real-World Validation & Release Readiness

### Score B — Validation and release readiness: **35 / 100**

| Category | Weight | Category score | Weighted | Why |
|---|---:|---:|---:|---|
| Backend and architecture | 15 | 45% | 6.75 | Runs live, but single-process stdlib server, hardcoded model identity, no deployment/auth story. |
| Frontend and user experience | 15 | 30% | 4.50 | Cannot work on any port but 8000; static city list replaces live geocoding; unrelated landing shell. |
| Routing and integrations | 10 | 55% | 5.50 | Live routes verified, but depends on public demo services with no SLA/local fallback and no outage soak test. |
| Hazard detection pipeline | 10 | 10% | 1.00 | Genuine v2 absent; smoke substitute served as v2; independent performance unknown. |
| Deterministic risk and safety | 15 | 50% | 7.50 | Safety suppression verified, but inputs come from an unvalidated model; invalid coords default silently; severity metadata stale. |
| LLM grounding | 5 | 50% | 2.50 | Deterministic fallback is safe; live grounded LLM behaviour not verified. |
| Dataset and evaluation | 10 | 5% | 0.50 | Nothing independent exists; freeze refused; 0 approved sources. |
| Testing and reliability | 10 | 35% | 3.50 | Unit/hermetic suite strong; no independent eval, no CI browser E2E, no resilience soak. |
| Security and deployment | 10 | 30% | 3.00 | No authentication, authorization, rate limiting, TLS, or deployment packaging. |
| **Total** | **100** | — | **34.75 ≈ 35** | |

**Interpretation:** a release decision cannot be supported. Two independent blockers alone (false model identity and absent independent validation) cap readiness far below release candidate.

---

## 5. Test Execution Results

**Command executed (exact):**

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

| Metric | Result |
|---|---|
| Python | 3.12.10 (CPython) |
| Platform | Windows-11-10.0.26300-SP0 |
| Test files | 34 |
| Total tests | **459** |
| Passed | **459** |
| Failed | **0** |
| Skipped | **0** |
| Errors | **0** |
| Duration | **76.370 s** |
| Exit code | **0** |
| Failure details | None |

**Verdict: PASS (VERIFIED).** The suite is green. Note that a green suite here means *hermetic behavioural correctness*, not model accuracy or real-world safety.

**Targeted coverage present in that same run** (not separately re-run; the discover command executed all of them):

| Area | Test module(s) | Result |
|---|---|---|
| Risk engine | `test_risk_engine.py`, `test_hazard_aggregation.py`, `test_stale_fresh_regression.py` | included, all pass |
| Routing | `test_routing_adapter.py`, `test_multi_routing_adapter.py`, `test_route_recommendation_correctness.py` | included, all pass |
| Detection | `test_detection.py`, `test_detection_matching.py`, `test_detection_outcome.py`, `test_preprocessing.py`, `test_threshold_consistency.py` | included, all pass |
| Dataset governance | `test_dataset_leakage.py`, `test_phase43_governance.py`, `test_artifact_audit.py` | included, all pass |
| Phase 42 evaluation | `test_independent_evaluator.py` | included, all pass |
| API contracts | `test_api.py`, `test_end_to_end_api.py`, `test_facilities_api.py` | included, all pass |
| Frontend/backend contract | exercised manually via headless Chrome/CDP (below); no automated browser test exists | NOT TESTED in suite |

---

## 6. Backend Test Results

**Startup (VERIFIED):** `.venv\Scripts\python.exe scripts\run_app.py --no-browser --port 8000` launched the stdlib server serving API + static UI.

| Check | Input | Result | Evidence |
|---|---|---|---|
| Health | `GET /api/health` | **200**, `status: ok`, providers `{routing: multi, imagery: mapillary, facilities: overpass, geocoding: nominatim, llm: ollama}` | VERIFIED |
| Config redaction | `GET /api/config` | **200**; only `mapillary_token_present: true`; no token value | VERIFIED |
| UI root | `GET /` | **200**, serves `frontend/index.html` | VERIFIED |
| Static assets | `GET /favicon.svg`, `/assets/index-CXsvefbt.js` | **200** | VERIFIED |
| Unknown API | `GET /api/nope` | **404** `not_found` | VERIFIED |
| Unknown analysis | `GET /api/analyze/does-not-exist` | **404** `not_found` | VERIFIED |
| Missing destination | `POST /api/analyze {}` | **400** `invalid_request` | VERIFIED |
| Empty geocode | `POST /api/geocode {}` | **400** `invalid_request` | VERIFIED |
| Empty facilities | `POST /api/facilities {}` | **400** `invalid_request` | VERIFIED |
| Invalid JSON | `POST /api/routes` malformed | **400** `invalid_request` | VERIFIED |
| CORS preflight | `OPTIONS /api/routes` | **204**, `Access-Control-Allow-Origin: *` | VERIFIED |
| **Invalid coordinate** | origin `latitude: 999` | **200 OK** with hardcoded Bengaluru default (`origin_resolution: "default"`) instead of 400 | **FAIL (VERIFIED)** |
| Path traversal | encoded `../` probes | no file leak; SPA `index.html` returned | PASS (VERIFIED) |
| DB connectivity | `data/saferoute.db` | SQLite opens; tables `model_versions, searches, analyses, scores, hazard_detections` | VERIFIED |
| Logging | server logging | `log_message` suppressed/secret-free; no token logged | CODE-VERIFIED |

**Database state (read-only):** 47 searches, 47 analyses, 96 scores, 58 hazard detections, **0 model_versions**. The empty `model_versions` table means the system records model identity only as the hardcoded string, not as a verifiable artifact record.

**Verdict:** backend API surface is functional and mostly well-validated. The invalid-coordinate auto-default is a real safety/contract defect: a caller who sends a malformed origin gets a different, valid-looking location instead of an error.

---

## 7. Frontend Test Results

**Method:** headless Google Chrome (`--headless=new --remote-debugging-port=9222`) driven via the Chrome DevTools Protocol using Node 26.13.0. Playwright/Selenium were absent; CDP was used instead. This is real browser execution, not DOM scraping of a static file.

| Check | Result | Evidence |
|---|---|---|
| Application loads | **PASS** — branded **INDROUTE / “THE WORLD IS A BOOK”** landing page at `/` | VERIFIED (screenshot + DOM) |
| Navigate to app | **PASS** — `EXPLORE` → `/search` | VERIFIED |
| Map renders | **PASS** — MapLibre canvas (`.maplibregl-map`), OpenFreeMap/OpenMapTiles attribution | VERIFIED |
| Map controls | **PASS** — zoom in/out, locate-me, Roads/Parks/Buildings layer pills | VERIFIED |
| Origin/destination entry | **PASS** — comboboxes with place suggestions and keyboard support | VERIFIED |
| **Live geocoding in UI** | **FAIL** — suggestions come from a bundled hardcoded list of ~23 world cities + Bengaluru localities; no `/api/geocode` call | VERIFIED (bundle inspection + `performance` had no `/api/geocode`) |
| Route request reaches backend | **PASS on port 8000** — `POST http://localhost:8000/api/routes` then `/api/analyze` | VERIFIED (CDP Network events) |
| Backend base configurable | **FAIL** — bundle hardcodes `Z2 = "http://localhost:8000"` and `baseUrl ?? "http://localhost:8000"` | VERIFIED (bundle) |
| Alternatives display | **PASS** — “4 distinct routes returned by the routing provider” (Route 1–4) | VERIFIED |
| Hazard info | **PASS** — per-route hazard counts and details (e.g., 4 potholes on Route 1) | VERIFIED |
| Risk comparison | **PASS** — scores shown; “Safest route cannot currently be determined” with reason | VERIFIED |
| Facilities | **PASS** — nearby facilities counts + medical access section | VERIFIED |
| Loading state | **PASS** — explicit pipeline stages while pending | VERIFIED |
| Empty/insufficient state | **PASS** — “No route is scored or recommended here” | VERIFIED |
| Backend-failure honesty | **PASS** — on wrong port: “SafeRoute backend is unreachable at http://localhost:8000 … No route result is shown.” | VERIFIED |
| JS errors during flow | **PASS** — none captured | VERIFIED |
| Product/name consistency | **FAIL** — landing page is a generic travel brand, not SafeRoute; README instructs “click Analyze safety”, UI says “Plan safe route” | VERIFIED |
| Duplicate bundles | **FAIL (hygiene)** — 5 near-identical `index-*.js` (~1.58 MB each; 7.92 MB total) and multiple `Loader-*.js` | VERIFIED |

**Full browser E2E (port 8000, VERIFIED):** Bengaluru → Whitefield → `Plan safe route` → 4 genuine routes → honest pending state (“No score or recommendation exists yet”) → after ~140 s, 4 assessed/stale routes with scores **97.36 / 98.6 / 99.31 / 96.81**, hazard details, facilities, “Safest route cannot currently be determined”, fallback explanations, no JS errors, no fabricated safe recommendation.

**Key UX finding:** the UI is honest and well-designed *once it can reach the backend*, but it is coupled to one hardcoded origin and a static city list. That is prototype wiring, not release wiring.

---

## 8. Routing Test Results

**Executed (VERIFIED):**

```json
POST /api/routes
origin      = 12.9716, 77.5946
destination = 12.9352, 77.6245
```

Response: **HTTP 200**, `status: ok`, `provider: multi`, `providers: ["osrm","valhalla"]`, `routes_count: 4`.

| Route | Provider | Distance | Duration | Coordinates | Invalid coords | Segments |
|---|---|---:|---:|---:|---:|---:|
| `rt-osrm-a505-00` | osrm | 7,503.0 m | 737.4 s | 241 | 0 | 38 |
| `rt-osrm-a505-01` | osrm | 8,694.7 m | 740.2 s | 283 | 0 | 41 |
| `rt-val-24d5-00` | valhalla | 8,305.0 m | 1,647.4 s | 283 | 0 | 35 |
| `rt-val-24d5-01` | valhalla | 8,291.0 m | 1,686.1 s | 315 | 0 | 35 |

**Checks**

| Requirement | Result | Evidence |
|---|---|---|
| Real routing integration | **PASS** | Live OSRM + Valhalla responses | VERIFIED |
| Route geometry validity | **PASS** | All coordinate pairs within lon/lat bounds; 0 invalid | VERIFIED |
| Distance/duration handling | **PASS** | Positive metres/seconds, plausible for Bengaluru | VERIFIED |
| Alternatives | **PASS** | 4 distinct midpoints, two providers | VERIFIED |
| No synthetic routes | **PASS** | `multi_adapter` composes only returned candidates; no padding to 4 | CODE-VERIFIED |
| No fabricated alternatives | **PASS** | De-dup is geometric; short-route run returned only 2 routes | VERIFIED + CODE-VERIFIED |
| Failure/timeout behaviour | **PASS (code)** | Bounded timeouts (OSRM 5 s ×3, Valhalla 8 s ×2) and explicit `PROVIDER_TIMEOUT`/`PROVIDER_ERROR` | CODE-VERIFIED |
| Unsafe fallback recommendation | **PASS** | Provider failure is disclosed; recommendation suppressed | CODE-VERIFIED |
| Mock routes auto-substituted | **PASS (no)** | `config/routing.yaml` default is `multi`; mock only when explicitly selected/unknown provider | CODE-VERIFIED |
| Public-service dependence | **RISK** | Relies on `router.project-osrm.org` and `valhalla1.openstreetmap.de`; no SLA/local instance | VERIFIED |

**Verdict:** routing is one of the strongest parts of the project. It returns only genuine provider routes and states limitations honestly.

---

## 9. Detection and Model Status

### Checkpoint facts (VERIFIED)

| Artifact | SHA-256 | Size |
|---|---|---:|
| `models/training/saferoute-yolo11-v2/weights/best.pt` (canonical serving path) | `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` | 5,443,482 B |
| `models/training/saferoute-yolo11-v1/weights/best.pt` | `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` | identical |
| `models/training/p0-smoke/weights/best.pt` | `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` | identical |
| `models/training/p0-smoke/weights/last.pt` | `7BA35DF6AE49C71C746E78AC714F62CC87B4882777286481F98A1427DDF8D5BC` | — |
| Documented genuine v2 hash | `B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA` | **no matching file found** |

`models/training/saferoute-yolo11-v2/P0_SMOKE_SUBSTITUTE.json` states:

> `"status": "NON_PRODUCTION_P0_SMOKE_SUBSTITUTE"` … *“This file is a copy of the P0 smoke model, NOT the original saferoute-yolo11-v2 artifact. The original checkpoint was not recoverable. Do not use for safety claims or production evaluation.”*

### Identity misrepresentation (FAIL — VERIFIED)

| Surface | Reported value |
|---|---|
| `GET /api/health` | `model_version: "saferoute-yolo11-v2"` |
| `GET /api/config` | `model_version: "saferoute-yolo11-v2"` |
| `POST /api/analyze` | `model_version: "saferoute-yolo11-v2"` |
| UI result record | `saferoute-yolo11-v2` |
| Actual loaded file | P0 smoke substitute |

**This is a direct violation of the required rule “The P0 smoke substitute must never be treated as the genuine v2 model.”**

### Configuration (VERIFIED)

| Setting | `config/detection.yaml` | `config/hazard_severity.yaml` | Consistent? |
|---|---|---|---|
| Confidence | `inference.conf: 0.25` | `thresholds.confidence_threshold: 0.25` | **YES** |
| Supported classes | `0: pothole`, `1: crack` | base severities for pothole/crack | YES |
| Unsupported classes | manhole, damaged_patch, waterlogging, uneven_surface, speed_bump | `unsupported: 1.0` bucket | disclosed |
| Model version metadata | `saferoute-yolo11-v2` | **`saferoute-yolo11-v1` (stale)** | **NO** |

### Detection execution (VERIFIED — functionality only)

- `/api/analyze` processed **27 of 39** retrieved images in 7.84 s detection time.
- Route 1 recorded 4 potholes; hazards were aggregated and scored.
- These detections come from the smoke substitute. They demonstrate that the pipeline runs; they are **not** detector-performance evidence and **not** a safety claim.

### Independent evaluation

**BLOCKED / NOT_ASSESSED.** `reports/phase42_independent_evaluation.json` has `status: "NOT_ASSESSED"`, `evaluation_executed: false`, and refuses the smoke checkpoint. Phase 40 metrics (`mAP50 0.0423`, `mAP50-95 0.0121`, precision 0.114, recall 0.094) are **REPORTED**, not independent. README’s `mAP@0.5 ≈ 0.26` is **REPORTED but unverified and inconsistent** with Phase 40.

**Verdict:** detection code is complete; the *model identity and validation evidence are not releasable*.

---

## 10. Risk Engine Safety Results

| Requirement | Result | Evidence |
|---|---|---|
| Only `DeterministicRiskEngine` computes risk | **PASS** | Single scoring path in `src/risk/engine.py`; comparison consumes scores only | CODE-VERIFIED |
| Missing evidence never becomes safe | **PASS** | Unassessed status; no score fabricated | VERIFIED (API/UI) |
| Stale evidence never becomes safe | **PASS** | Live run: scores shown but recommendation `None`, reason `no_sufficiently_assessed_route` | VERIFIED |
| Failed evidence never becomes safe | **PASS** | Failure/insufficient paths produce unassessed, not zero-hazard-safe | CODE-VERIFIED |
| Insufficient coverage suppressed | **PASS** | `assessed_length_fraction` + policy threshold gate recommendation | CODE-VERIFIED |
| Hazard severity aggregation | **PASS** | Config-driven `severity.py`; conf 0.25 aligned | VERIFIED (config) + CODE-VERIFIED |
| Segment distance handling | **PASS** | Segmentation policy 50–500 m; per-segment evidence | CODE-VERIFIED |
| Tie handling | **PASS** | Tied top scores → no recommendation | CODE-VERIFIED |
| Recommendation eligibility | **PASS** | Minimum coverage + non-stale + non-demo + tie rules | CODE-VERIFIED |
| Facilities excluded from scoring | **PASS** | Facilities service separate; risk engine never receives facilities | CODE-VERIFIED |
| LLM grounding | **PASS (fallback)** | Validator rejects unknown entities/scores; deterministic fallback used | CODE-VERIFIED + VERIFIED (fallback source) |
| Production formula/thresholds unchanged | **PASS** | Config hashes unchanged: detection `22371AE8…B18344`, severity `D11AA0F7…CDF473`, runtime `61B8143B…621D01` | VERIFIED |
| Invalid origin handling | **FAIL** | `latitude 999` silently becomes `12.9716, 77.5946` | VERIFIED |
| Severity model metadata | **FAIL (minor)** | `hazard_severity.yaml` still declares v1 | VERIFIED |

**Safety analysis of the live run:** scores were **100.0** and **93.11** on a short route with 0 and 2 hazards respectively, `evidence_class: "stale"`, recommendation `null`. Showing a numeric score for stale evidence is defensible *only because* the recommendation is suppressed and the limitation is disclosed. The UI does exactly that: “No route is presented as safe.”

**Verdict:** the deterministic safety core behaves correctly and honestly. The residual risks are input validation and unvalidated detector inputs — not the scoring formula.

---

## 11. Dataset / Evaluation Status

| Item | Status | Evidence |
|---|---|---|
| `data/independent/` | **ABSENT** | `Test-Path` false | VERIFIED |
| Approved independent sources | **0** | `reports/phase43_source_audit.json` | VERIFIED |
| Source registry | Proxy-only / `reference_only: true`, `approved_for_acquisition: false` | `docs/datasets/sources.yaml` | VERIFIED |
| Reference session registry | Filename date proxies (`verified: "false"`), no camera/route IDs | `reports/phase43_reference_registry.json` | VERIFIED |
| Acquisition plan | Documented | REPORTED |
| Annotation specification | Documented | REPORTED |
| Review/adjudication records | None real; governance tooling only | VERIFIED |
| Dataset freeze | **REFUSED** (`dataset_missing`) | `reports/phase43_freeze.json` | VERIFIED |
| Dataset hashes | None for an independent set | VERIFIED |
| Leakage checks | Tooling + tests exist; cannot run on absent data | CODE-VERIFIED |
| Phase 42 preflight | **NOT_ASSESSED** | `reports/phase42_independent_evaluation.json` | VERIFIED |
| Phase 43 P2/P3 | Tooling DELIVERED; dataset NOT CREATED; evaluation BLOCKED | `docs/reports/PHASE_43_P2_P3.md` | REPORTED/VERIFIED |

**Verdict:** there is **no real independent imagery, no verified reference registry, and no valid model accuracy claim**. Every detector number in the repo is either derived/same-source or stale. This is a hard release blocker.

---

## 12. Security and Deployment Findings

### Strengths (VERIFIED / CODE-VERIFIED)

| Control | Finding |
|---|---|
| Secret redaction | `Settings.to_safe_dict()` removes `mapillary_token`; `/api/config` exposed only `mapillary_token_present` (VERIFIED) |
| `.env` hygiene | `.env` git-ignored; only key name `MAPILLARY_ACCESS_TOKEN`; `.env.example` placeholders only (VERIFIED) |
| No token logging | Only a comment says the access token is fingerprinted, never stored; no token logging found |
| Path traversal | `_serve_static` resolves and enforces `relative_to(static_dir)`; encoded traversal probes leaked nothing (VERIFIED) |
| Timeouts | Routing 5–8 s, Mapillary 15 s, LLM bounded (default 45 s) (CODE-VERIFIED) |
| Bounded retries | OSRM 3, Valhalla 2, exponential backoff (CODE-VERIFIED) |
| Error envelope | Consistent `{status, error:{code, message, detail}}` (VERIFIED) |
| Dependency pinning | `requirements.txt` pins torch/vision/ultralytics/opencv/numpy/PyYAML (VERIFIED) |

### Weaknesses / gaps

| Issue | Severity | Evidence |
|---|---|---|
| No authentication or authorization on any endpoint | High | `/api/analyze` callable by anyone | VERIFIED |
| No rate limiting / abuse protection | High | External paid-ish services (Mapillary) callable freely | CODE-VERIFIED |
| CORS `Access-Control-Allow-Origin: *` | Medium | Any origin can call API | VERIFIED |
| Plain HTTP, no TLS | Medium | Local launcher only | CODE-VERIFIED |
| No container/deployment manifest, healthcheck, process manager | Medium | Repo has scripts only | VERIFIED |
| Single-threaded-ish stdlib server defaults | Medium | `ThreadingHTTPServer` assumed; no load test | NOT TESTED |
| Public demo routing dependencies | Medium | No local OSRM/Valhalla deployment | VERIFIED |
| Error detail may echo upstream strings | Low | `detail` includes provider/broken text | CODE-VERIFIED |
| Dependency vulnerability scan | NOT TESTED | No `pip-audit`/`safety` available/run | NOT TESTED |
| SQLite is single-file, no migrations | Low | Tables present; no migration framework | VERIFIED |

**Verdict:** reasonable defensive basics, but this is a developer-laptop service, not a deployable production service. No intrusive/destructive security testing was performed.

---

## 13. End-to-End Workflow Results

| # | Intended step | Result | Evidence |
|---|---|---|---|
| 1 | User opens SafeRoute AI | **PASS** | `/` loads (INDROUTE landing), `EXPLORE` → `/search` map UI | VERIFIED |
| 2 | User enters origin and destination | **PASS (static list)** | Combobox suggestions from bundled ~23-city list; no live geocoding call | VERIFIED |
| 3 | Backend geocodes locations | **FAIL (in UI) / PASS (API)** | UI never calls `/api/geocode`; API does geocode correctly | VERIFIED |
| 4 | Routing service returns genuine routes | **PASS** | 4 real OSRM + Valhalla routes | VERIFIED |
| 5 | Imagery obtained where available | **PASS (partial)** | 39 images retrieved, 27 used; stale classification | VERIFIED |
| 6 | Detector processes available imagery | **PASS (smoke model)** | 7.84 s detection; 4 potholes on Route 1 | VERIFIED |
| 7 | Backend aggregates verified hazards | **PASS** | `hazard_counts`, per-segment records | VERIFIED |
| 8 | `DeterministicRiskEngine` calculates risk | **PASS** | Scores 97.36–99.31 in UI; 100.0/93.11 in API run | VERIFIED |
| 9 | Route comparisons apply eligibility | **PASS** | `no_sufficiently_assessed_route`; no recommendation | VERIFIED |
| 10 | Facilities displayed as context | **PASS** | Counts + medical access; explicit straight-line caveat | VERIFIED |
| 11 | LLM explains verified results or safe fallback | **PASS (fallback)** | `source: "fallback"`; grounded-safe text | VERIFIED |
| 12 | Frontend displays final result | **PASS** | 4 routes, scores, hazards, facilities, honest limitation | VERIFIED |

**End-to-end verdict:** the workflow is genuinely functional **on port 8000 with static place selection**. The intended “live geocode from the search box” step is **FAIL**, and the whole flow is **BLOCKED** on any other port.

---

## 14. Critical Blockers

| # | Blocker | Evidence | Impact |
|---|---|---|---|
| B1 | **Smoke substitute served as genuine `saferoute-yolo11-v2`** | Canonical hash = P0 smoke hash; marker says non-production; health/config/analysis all say v2 | False model provenance; invalidates any safety claim; violates explicit rule |
| B2 | **Genuine v2 checkpoint missing** | Documented hash has no file; marker says original unrecoverable | Cannot evaluate or release the intended model |
| B3 | **No independent dataset / evaluation** | `data/independent/` absent; Phase 42 `NOT_ASSESSED`; 0 approved sources; freeze refused | No defensible accuracy/safety validation |
| B4 | **Frontend hardcodes `http://localhost:8000`** | Bundle `Z2` and `baseUrl` literals | UI fails entirely on documented `--port`; no deployment flexibility |
| B5 | **Invalid coordinates silently default to Bengaluru** | `origin latitude 999` → 200 + `origin_resolution: "default"` | Callers can analyze the wrong city without an error |
| B6 | **Shipped UI is a different product shell with static city list** | INDROUTE landing; ~23 hardcoded cities; no `/api/geocode` | User cannot search arbitrary real places; product mismatch |
| B7 | **Stale/contradictory documentation and metrics** | PRD/TRD/ARCHITECTURE say not implemented; README mAP ≈0.26 vs Phase 40 0.0423; severity metadata says v1 | Misleads reviewers/operators; undermines reproducibility |

---

## 15. Prioritized Remaining Work

### P0 — Critical blockers (must fix before any release/safety claim)

**P0-1. Stop presenting the smoke substitute as `saferoute-yolo11-v2`.**
- **Problem:** All surfaces report v2 while the loaded file is the P0 smoke copy.
- **Evidence:** Identical SHA-256 for v1/v2/smoke best.pt; `P0_SMOKE_SUBSTITUTE.json`; `/api/health`, `/api/config`, `/api/analyze`.
- **Files:** `src/api/pipeline.py` (`MODEL_VERSION`), `src/detection/detector.py`, `config/detection.yaml`, `src/api/app.py`, frontend result rendering.
- **Why it matters:** It is a false provenance/safety claim and an explicit rule violation.
- **Effort:** 0.5–1 day.
- **Dependencies:** None.
- **Fix:** Resolve model identity from the checkpoint marker/metadata and propagate it; report `NON_PRODUCTION_P0_SMOKE_SUBSTITUTE` everywhere; block “assessed/safe” language when the artifact is non-production. Do not rename the file to hide it.

**P0-2. Obtain and validate the genuine v2 checkpoint (or formally withdraw v2 claims).**
- **Problem:** No genuine v2 artifact exists.
- **Evidence:** Documented hash `B6354A…00BA` has no matching file; canonical path is a copy.
- **Files:** `models/training/saferoute-yolo11-v2/weights/best.pt`, `config/detection.yaml`, model registry.
- **Why it matters:** Without the intended artifact there is no model to release.
- **Effort:** 1–3 days (recover) or a retraining decision gate.
- **Dependencies:** Original artifact or approved retraining; Rule 19 gates.
- **Fix:** Restore the artifact, verify hash, register it in `model_versions`, update health/config, then re-run Phase 42.

**P0-3. Build and freeze a real independent evaluation set; run Phase 42.**
- **Problem:** `data/independent/` absent, 0 approved sources, freeze refused, evaluation `NOT_ASSESSED`.
- **Evidence:** Phase 42/43 JSON + report.
- **Files:** `data/independent/`, `docs/datasets/sources.yaml`, `scripts/phase43/`, `src/evaluation/`.
- **Why it matters:** No accuracy or safety claim is valid without it.
- **Effort:** 2–4 weeks (acquisition, annotation, adjudication).
- **Dependencies:** Licensed source, reviewers, verified session registry.
- **Fix:** Approve a licensed source, acquire imagery, annotate per spec, adjudicate, hash/freeze, run leakage checks, execute Phase 42.

**P0-4. Make the frontend backend base configurable and port-correct.**
- **Problem:** Bundle hardcodes `http://localhost:8000`.
- **Evidence:** `Z2`/`baseUrl` literals; UI failure on port 8765.
- **Files:** frontend source (not in repo; built `frontend/assets/index-*.js`), `scripts/run_app.py`, server config injection.
- **Why it matters:** The UI is unusable on any other port and cannot be deployed.
- **Effort:** 0.5–1 day.
- **Dependencies:** Frontend source project.
- **Fix:** Inject API base at build/runtime (relative `/api` preferred), remove hardcoded origin, add a contract test.

**P0-5. Reject invalid coordinates instead of defaulting.**
- **Problem:** `latitude 999` silently becomes Bengaluru.
- **Evidence:** `POST /api/routes` → 200 with `origin_resolution: "default"`.
- **Files:** `src/api/app.py` (`_parse_coordinate`, `_resolve_location`).
- **Why it matters:** Silent wrong-city analysis is unsafe.
- **Effort:** 0.5 day.
- **Dependencies:** None.
- **Fix:** Validate ranges; return 400 `invalid_request`; keep explicit default only for a documented, deliberate “use my location” path.

**P0-6. Reconcile model/threshold metadata and documentation.**
- **Problem:** Severity config says v1; docs claim no implementation; README mAP conflicts.
- **Evidence:** `config/hazard_severity.yaml`, `docs/PRD.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md`, `README.md`.
- **Files:** those files.
- **Why it matters:** Reviewers cannot trust reported state.
- **Effort:** 1 day.
- **Dependencies:** Decide the true model/metric source.
- **Fix:** Regenerate docs from actual state; one authoritative metrics section; state blockers explicitly.

### P1 — Important gaps

**P1-1. Replace the hardcoded city list with live `/api/geocode` search.**
- **Evidence:** Bundle `oW` list of ~23 cities; no geocode calls in `performance`.
- **Files:** frontend search component; `src/api/app.py` geocode handler.
- **Why:** Users cannot search real addresses.
- **Effort:** 1–2 days. **Deps:** none. **Fix:** debounce geocode, show backend candidates, fall back to static presets only as documented offline mode.

**P1-2. Make facilities/hazard/result semantics explicit in the UI for non-production models.**
- **Files:** frontend result rendering; explanation payload.
- **Why:** Prevent users reading smoke-model scores as real safety.
- **Effort:** 0.5 day. **Deps:** P0-1. **Fix:** banner + status from backend provenance.

**P1-3. Add authentication/rate limiting for any non-local deployment.**
- **Files:** `src/api/app.py`, deployment config.
- **Why:** Open compute/imagery abuse.
- **Effort:** 1–2 days. **Deps:** deployment target. **Fix:** token auth or reverse proxy with limits.

**P1-4. Add browser E2E and external-failure tests to CI.**
- **Files:** `tests/`, CI config.
- **Why:** Current 459 tests never touch the real UI wiring defects found here.
- **Effort:** 2–3 days. **Deps:** headless browser in CI. **Fix:** CDP/Playwright smoke test on a non-8000 port; simulate OSRM/Valhalla/Overpass/Mapillary failures.

**P1-5. Pin/verify model artifact registration in DB.**
- **Files:** `src/api/store.py`, `model_versions`.
- **Why:** Table has 0 rows; provenance not persisted.
- **Effort:** 0.5 day. **Deps:** P0-2. **Fix:** register checkpoint hash/status at bootstrap and link analyses to it.

**P1-6. Clean bundle/asset duplication and align product branding.**
- **Evidence:** 5 near-identical index bundles, 7.92 MB; INDROUTE shell.
- **Files:** `frontend/assets/`, `frontend/index.html`.
- **Why:** Confusing UX and slow loads.
- **Effort:** 0.5–1 day. **Deps:** frontend source. **Fix:** rebuild once, delete stale bundles, unify SafeRoute branding or document the INDROUTE shell.

### P2 — Post-release improvements

| Item | Problem | Files | Effort | Fix |
|---|---|---|---|---|
| P2-1 Local routing instances | Public demo dependency/SLA | `config/routing.yaml` | 2–3 days | Self-host OSRM/Valhalla |
| P2-2 Structured logging/metrics | Logs suppressed; no observability | `src/api/app.py` | 1–2 days | Secret-safe structured logs, request IDs, metrics |
| P2-3 SQLite → managed DB | Single-file store, no migrations | `src/api/store.py` | 2–4 days | Migration framework / Postgres |
| P2-4 Dependency scanning | No `pip-audit` run | CI | 0.5 day | Add audit job |
| P2-5 Response caching | Repeat analyses expensive | pipeline/cache | 1–2 days | Content-addressed cache |
| P2-6 Load/soak testing | Unknown concurrency limits | tests | 1–2 days | k6/Locust scenario |
| P2-7 Offline/demo mode clarity | Mock exists but can confuse | `mock_adapter.py` | 0.5 day | Explicit UI “demo routes” badge |

---

## 16. Recommended Fastest Path to Completion

1. **Stop the bleeding (0.5–1 day):** fix model provenance reporting (P0-1), reject invalid coordinates (P0-5), correct docs/config metadata (P0-6).
2. **Restore the real model (1–3 days):** recover/verify `saferoute-yolo11-v2` and register its hash (P0-2, P1-5). If unrecoverable, formally redefine the release baseline instead of pretending.
3. **Fix the client (1–2 days):** configurable API base + live geocode search + provenance banner (P0-4, P1-1, P1-2).
4. **Create validation evidence (2–4 weeks):** licensed independent dataset → annotation/adjudication → freeze + leakage checks → Phase 42 evaluation (P0-3). This is the long pole and cannot be shortcut.
5. **Harden (3–5 days):** auth/rate limiting, CI browser E2E, failure injection, deployment manifest (P1-3, P1-4).
6. **Re-audit:** only after steps 1–5 should the project be considered for a release-candidate classification.

---

## 17. Commands and Evidence Used

```powershell
# Full existing suite (VERIFIED)
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
# 459 tests, OK, 76.370 s, 0 failures, 0 skips, 0 errors, exit 0

# Environment
.venv\Scripts\python.exe --version          # Python 3.12.10
# Platform: Windows-11-10.0.26300-SP0

# Backend (documented launcher, background)
.venv\Scripts\python.exe scripts\run_app.py --no-browser --port 8000
# also exercised on --port 8765 (UI failure demonstrates hardcoded base)

# Checkpoint hashes
Get-FileHash models\training\saferoute-yolo11-v2\weights\best.pt -Algorithm SHA256
Get-FileHash models\training\p0-smoke\weights\best.pt -Algorithm SHA256
Get-Content models\training\saferoute-yolo11-v2\P0_SMOKE_SUBSTITUTE.json

# Live API probes (VERIFIED)
GET  /api/health          -> 200
GET  /api/config          -> 200 (token redacted)
GET  /                    -> 200
GET  /api/nope            -> 404
POST /api/analyze {}      -> 400
POST /api/geocode {}      -> 400
POST /api/facilities {}   -> 400
POST /api/routes invalid  -> 200 (FAIL: defaults to Bengaluru)
POST /api/routes valid    -> 200, 4 genuine routes
POST /api/geocode         -> 200 Nominatim; gibberish -> no_results
POST /api/facilities      -> 200, 29 records, OSM attribution
POST /api/analyze valid   -> 200 in 58.1 s; scores 100.0/93.11; evidence stale; recommendation null

# Frontend (VERIFIED)
# Headless Chrome + CDP on port 9222, Node 26.13.0
# / -> INDROUTE landing; EXPLORE -> /search; MapLibre canvas; 2 inputs; controls
# Bengaluru -> Whitefield -> Plan safe route
# 4 routes pending -> ~140 s -> 4 assessed/stale routes, scores 97.36/98.6/99.31/96.81
# "Safest route cannot currently be determined"; no JS errors

# Governance evidence
Get-Content reports\phase42_independent_evaluation.json   # NOT_ASSESSED
Get-Content reports\phase43_freeze.json                   # REFUSED, dataset_missing
Get-Content reports\phase43_source_audit.json             # 0 approved sources
Get-Content reports\phase43_reference_registry.json       # proxy-only, unverified

# Database (read-only)
# data/saferoute.db: 47 searches, 47 analyses, 96 scores, 58 hazard_detections, 0 model_versions
```

**Evidence artifacts generated outside the repo (temporary, not part of the project):**
`sr_dom.html`, `sr_shot.png`, `sr_ui_results.png`, and CDP scripts under `C:\Users\pushk\AppData\Local\Temp\`.

---

## 18. Explicit Limitations and Untested Components

1. **No genuine v2 model:** all detection outputs are from the P0 smoke substitute; no detector accuracy, recall, precision, or safety claim is made by this audit.
2. **Independent evaluation not performed:** `data/independent/` absent, 0 approved sources, freeze refused, Phase 42 `NOT_ASSESSED`. Reported Phase 40 metrics are not reproduced.
3. **External services were reachable during this audit** (OSRM, Valhalla, Nominatim, Overpass, Mapillary) but are environment-dependent; no outage/soak/rate-limit testing was done.
4. **Live Ollama-grounded prose was not verified.** Observed explanations came from the deterministic fallback; the grounding validator was inspected, not exercised against live model output.
5. **Browser testing used CDP, not Playwright/Selenium** (neither is installed). Interaction coverage was real but not exhaustive (e.g., keyboard-only paths, every error branch, mobile viewport).
6. **No load, concurrency, memory, or long-running stability testing** was performed.
7. **No dependency vulnerability scan** (`pip-audit`/`safety`) was available/run.
8. **No security exploitation testing** was performed beyond safe path-traversal probes and secret-exposure checks.
9. **Uncommitted Phase 42/43 work** was inspected read-only; this audit did not commit, stage, or push it.
10. **`master_rules.md` workspace path mismatch:** it references `D:\New folder (3)`, while the actual repo is `D:\COde\Major project\Saferoute-AI-Project`; rules were applied to the actual repo but the documented path is stale.
11. **Frontend source is not present in the repo** (only built assets); frontend defects were diagnosed from the bundle and runtime, not from source.
12. **No production deployment was tested**; no container/orchestrator manifest exists.

---

## Final Classification

**ADVANCED PROTOTYPE**
