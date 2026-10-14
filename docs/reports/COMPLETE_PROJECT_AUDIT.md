# SafeRoute AI — Complete Project Audit (READ-ONLY)

> **Date:** 2026-10-14 · **Workspace:** `D:\New folder (3)`
> **Type:** read-only audit — no code changed, no model retrained, no files deleted,
> no dependencies installed, no datasets downloaded **during this audit**.
> **Governing:** `master_rules.md` (authoritative), `docs/TRAINING_RULES.md`,
> `docs/PRD.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md`.
> **Evidence rule:** a status is PASS only with executed evidence; code existing ≠ works.

## 1. Executive summary

SafeRoute AI is a working **functional prototype** with a real, end-to-end
pipeline (routing → imagery → OpenCV → YOLO11 → aggregation → deterministic risk
→ grounded explanation → UI), a trained 2-class detector, a stdlib backend with
SQLite persistence, and a static map UI. The **core deterministic chain is solid
and tested (119 tests)**, but there are **accuracy, security and real-imagery
gaps** that block production use.

**Headline facts (measured this audit):**
- Tests: **119 run, 118 pass, 1 fail** (the failure is a new regression test that
  intentionally exposes a real defect — see §5).
- Live providers: **Nominatim geocoding OK (3 candidates)**; **OSRM OK → 2 genuine
  routes** (honest "fewer than four", never padded). **Live Mapillary and Ollama
  NOT enabled** (no `.env`): imagery uses a demo local fallback, explanations use
  the deterministic fallback.
- Detector: loads `saferoute-yolo11-v1/weights/best.pt` (sha256 `61F6EDA2…`),
  classes `{0:pothole, 1:crack}`; accuracy is **low** (40-image labelled sample:
  P≈0.14–0.19, R≈0.17–0.22).
- **Critical defect:** detector `conf=0.15` ≠ aggregator `confidence_threshold=0.25`
  → 36% of detections silently dropped; a covered segment with 0 surviving hazards
  scores **100** ("no detection" is not distinguished from "safe").
- Security: **no authentication, no rate limiting, `Access-Control-Allow-Origin: *`**.

**Verdict: functional MVP / advanced prototype — NOT production-ready** (§12).

## 2. Architecture & data flow

```
User (frontend/index.html + app.js, Leaflet map)
  → POST /api/geocode   (Nominatim, keyless)          [live OK]
  → POST /api/routes    (OSRM, keyless; mock fallback) [live OK, 2 routes]
  → POST /api/analyze   (src/api/pipeline.py orchestrates)
        routing.adapter → imagery.adapter → OpenCV preprocessing
        → detection.detector (YOLO11 best.pt)
        → risk.aggregate (severity policy, dedup)
        → risk.engine (deterministic S=100·exp(-λ·H))
        → llm.explainer (Ollama or deterministic fallback)
  → SQLite (src/api/store.py)  → GET /api/analyze/{id}, /comparison, /hazards, /explanation
```

- Backend = **standard library `http.server`** (FastAPI/MySQL in the TRD are
  *not* used; SQLite substituted — documented deviation, Rule 19/18).
- Frontend = dependency-free HTML/CSS/JS + Leaflet **CDN** (React not used).
- 11 config files under `config/`; 5 governing docs; 22 phase reports.
- Persistence verified: `data/saferoute.db` — tables `model_versions, searches,
  analyses, scores, hazard_detections`; 1 analysis, 2 scores stored.

## 3. Test commands & actual results (executed)

| Command | Result |
|---|---|
| `.\.venv\Scripts\python.exe -m unittest discover -s tests -t .` | **Ran 119, 1 failure** (threshold-consistency, by design) |
| `... -m unittest tests.integration.test_end_to_end_api` | 10/10 OK |
| `... -m unittest tests.unit.test_preprocessing tests.unit.test_detection tests.unit.test_hazard_aggregation tests.unit.test_risk_engine tests.integration.test_end_to_end_pipeline` | 48/48 OK |
| Live Nominatim + OSRM one-shot check | GEO ok 3 · OSRM ok 2 routes |
| SQLite schema/counts | 5 tables; analyses=1, scores=2 |

## 4. Feature-wise audit

| # | Feature | Required (docs) | Implementation | Evidence | Status |
|---|---|---|---|---|---|
| 1 | Frontend UI / map / search / location / routes | React + map, search, route display | Static HTML/JS + Leaflet CDN; search via `/api/geocode`; browser geolocation | Files exist; geocode live OK; served over HTTP (`test_serves_static_index`). No browser/headless test | PARTIAL |
| 2 | Backend / endpoints / validation / errors | FastAPI, 7 endpoints | stdlib `http.server`; 7 endpoints + `/geocode` + `/config` | 10/10 E2E API tests; error-schema test | PASS |
| 3 | Geocoding + routing providers | provider-independent | Nominatim + OSRM live; mock adapters | Live: GEO ok (3); OSRM ok (2) | PASS |
| 4 | Four-route comparison | show ≤4 genuinely returned, never pad | returns provider truth | Live OSRM=2; mock 1–3; limitation flag set | PASS |
| 5 | Imagery acquisition / matching / missing handling | permitted sources only | Mapillary (token) + local demo fallback; 25 m matcher; staleness | missing→`unassessed` tested; **live Mapillary NOT TESTED (no token)**; fallback anchors to fixed Bengaluru point | PARTIAL |
| 6 | OpenCV load/preprocess/visualise | 1 versioned pipeline | `preprocess-v1` | 15/15 tests; letterbox (640,640,3); validation codes | PASS |
| 7 | YOLO11 load / classes / accuracy / thresholds | pothole,crack, honest | `detect-v2`, best.pt | Loads (sha256 verified); sample P≈0.14,R≈0.22; **threshold mismatch** | PARTIAL |
| 8 | Aggregation + deterministic risk | S=100·exp(−λH), dedup, coverage | `severity-v1`, IoU dedup, engine | 12 risk + 10 aggregation tests; determinism verified | PASS* |
| 9 | LLM explanation / grounding / fallback | grounded, no fabrication | Ollama (disabled) + deterministic fallback; entity-grounding reject | 6/6 llm tests; fallback source verified | PASS* (live Ollama NOT TESTED) |
| 10 | Facilities (hospital/pharmacy/restaurant/hotel/fuel/police) | separate from score | mock + Overpass providers behind interface | mock 8/8 tests; separation guardrail test; **live Overpass NOT TESTED**; service default provider=mock | PARTIAL |
| 11 | DB / models / config / env vars | MySQL + config | SQLite (deviation) + 11 YAML configs + `.env.example` | DB opens, schema+rows; `.env` absent | PASS* (no MySQL) |
| 12 | Auth / security / privacy / rate limiting | secrets in `.env`, validation, limits | secrets via `.env`; input validation | **no auth, no rate limiting, CORS `*`; no upload size caps** | FAIL |
| 13 | Unit / integration / API / E2E tests | layered + negative | 15 test modules | **119 run, 1 fail** (by design); negative tests pass | PARTIAL |
| 14 | Dataset / splits / checkpoints / reproducibility | audited, leakage-safe | PHASE_03 audit + splits + run records | dataset audited; RDD2022 audited+dedup-scanned but **not converted**; checkpoints hashed | PARTIAL |
| 15 | Docs / scripts / deps / CI / deployment | reproducible setup | 5 docs + 22 reports + run scripts + pinned reqs | present; **no CI/CD, no container/deploy** | PARTIAL |

`*` = PASS for the tested surface, with the caveat stated. `#8` is PASS for
determinism but its **inputs** are affected by the §5 threshold defect (so the
end-to-end score can be misleading).

## 5. Critical bugs & root causes

| ID | Severity | Bug | Root cause | Impact | Evidence |
|---|---|---|---|---|---|
| B1 | **P0** | Detector `conf=0.15` vs aggregator `confidence_threshold=0.25`; 36% of detections silently dropped | two independent configs, no shared contract | true hazards in [0.15,0.25) never reach scoring | `test_threshold_consistency` FAILS `0.15 != 0.25`; 15-img scan: 56 raw → 20 dropped |
| B2 | **P0** | "Zero hazards → score **100.0**" conflates *no detection* with *safe road* | engine returns 100 when `H=0` on a covered segment | misleading safety score (spirit of Rule 9) | pipeline trace: 0 hazards → route_score 100.0, status assessed |
| B3 | P1 | Local-archive imagery fallback anchors samples to a **fixed Bengaluru point** regardless of segment | demo-only catalogue in `PermittedImageryAdapter` | spurious image↔segment matches for non-Bengaluru routes | code read + tests |
| B4 | P1 | Low detector accuracy | small/noisy single-source dataset; max_severity class imbalance | P≈0.14–0.19, R≈0.17–0.22 (40-img sample) | `reports/phase21_yolo_opencv/evidence.json` |
| B5 | P2 | Detector double-letterboxes (preprocessed 640² re-fed to `model.predict(imgsz=640)`) | pipeline preprocess + Ultralytics internal preprocess | redundant; future pad-mapping drift risk | `scripts/verify_yolo_opencv.py` output |

B1 and B2 are the highest-impact and both are **known, documented, not yet fixed**
(config change requires approval).

## 6. Missing / partial requirements

- FastAPI backend and MySQL were specified in the TRD but **not implemented**
  (stdlib HTTP + SQLite substituted; documented deviation).
- React frontend not implemented (static HTML/JS; documented deviation).
- Live Mapillary imagery and live Ollama explanations require credentials/runtime
  not present (`.env` absent).
- No authentication, rate limiting, API protection, or upload restrictions.
- No CI/CD, containerisation, or deployment artefacts.
- Four-route comparison is honest but the provider rarely returns four routes.

## 7. External services & credential dependencies

| Service | Key | Status |
|---|---|---|
| Nominatim (geocoding) | none | **live verified** |
| OSRM (routing) | none | **live verified (2 routes)** |
| Overpass (facilities) | none | implemented; **live NOT TESTED** |
| Mapillary (imagery) | `MAPILLARY_ACCESS_TOKEN` | **BLOCKED** (no token) |
| Ollama (LLM) | local runtime | **BLOCKED** (not running) |
| MySQL | creds | not used (SQLite) |

## 8. Dataset & model status

- Active dataset: `data/pothole_crack_manhole/data` (2009 imgs/labels, 3 classes,
  2 used) + `data/splits/{train,val,test}.txt` (1406/402/201). Audited PHASE_03.
- Serving checkpoint: `models/training/saferoute-yolo11-v1/weights/best.pt`
  sha256 `61F6EDA2…` (accepted PHASE_09). v1 test mAP@0.5 = 0.2615.
- v2 checkpoint exists (`saferoute-yolo11-v2`, best epoch 104, val mAP@0.5 0.287)
  — **not evaluated on the test set; no improvement claimed** and **not wired as
  the serving model** (`config/detection.yaml` still points at v1).
- RDD2022: downloaded (MD5 verified), extracted (6 countries, 30,224 train imgs),
  audit + duplicate scan done; **conversion/merge NOT done**; Norway excluded.
- Reproducibility: run records, config/hash manifests present.

## 9. Security & reliability gaps

- **No authentication** on any endpoint; **no rate limiting**; **CORS `*`**;
  no request body-size cap; no TLS (local only).
- Secrets: design is correct (`.env`, git-ignored) but `.env` is **absent**, so
  live imagery/LLM are off. No secret is committed.
- Reliability: error schema + negative tests present (routing failure, missing
  imagery, empty detections, LLM fallback). Missing: imagery/provider retry
  surfacing, degraded-mode banner, request timeouts on the API layer.
- Honesty: strong (unassessed vs safe; facilities separate; LLM grounding) — but
  B2 weakens the "100 = safe" interpretation.

## 10. Completion estimate (method + numbers)

**Method:** each area is scored on *verified-working* evidence only (code that
exists but was not executed counts as **not verified**). Area score = verified
sub-items ÷ required sub-items. This is an evidence-based judgement, **not** a
precision metric.

| Area | Verified working | Estimate |
|---|---|---|
| Core functionality | routing, geocoding, preprocessing, detection-run, aggregation, risk, explanation-fallback, API, persistence, comparison | **~75%** |
| ML / data pipeline | dataset audited, checkpoint trained/loaded, but low accuracy, threshold bug, RDD2022 not merged | **~55%** |
| Testing & reliability | 119 tests, strong unit/integration/negative; 1 fail; no browser/E2E-live; no CI | **~65%** |
| Security | secrets hygiene only; **no auth/ratelimit/CORS-restrict** | **~15%** |
| Documentation | 5 docs, 22 reports, README, run scripts | **~85%** |
| Production readiness | no auth, no CI/CD, no deploy, live data gaps, accuracy | **~20%** |

These percentages describe **verified functionality**, not lines of code.

## 11. Prioritized remaining work

| Pri | Task |
|---|---|
| **P0** | Align detector `conf` and aggregator `confidence_threshold` (single source); fix B1. |
| **P0** | Make B2 honest: distinguish `no_detections` from `assessed`; add a coverage/confidence disclosure so 100 isn't read as "safe". |
| **P1** | Provide `MAPILLARY_ACCESS_TOKEN`; verify live imagery + real image↔segment matching (fix B3 fallback). |
| **P1** | Improve detector accuracy (use the prepared RDD2022 dataset) and re-evaluate on the held-out test set before any claim. |
| **P1** | Add API auth (token), rate limiting, restrict CORS, body-size caps. |
| **P2** | Verify Overpass live facilities; verify Ollama live explanations. |
| **P2** | Evaluate v2 vs v1 on the test set; promote only if better (rollback policy). |
| **P2** | Finish RDD2022 conversion + leakage-safe splits + versioned dataset.yaml (PHASE_20). |
| **P2** | Add headless UI test + CI (run the 119-test suite). |
| **P3** | FastAPI/MySQL migration, containerisation, deployment docs. |

## 12. Exact commands for the next verification steps

```powershell
# Full test suite (expect 119 run, 1 known failure until B1 fixed)
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .

# Live provider checks (read-only)
.\.venv\Scripts\python.exe -c "from src.geocoding.nominatim import NominatimGeocoder as G;print(G().geocode('MG Road, Bengaluru',limit=3).status.value)"
.\.venv\Scripts\python.exe -c "from src.routing.osrm_adapter import OSRMRoutingAdapter as A;from src.routing.schemas import *;print(len(A().get_routes(RouteRequest(origin=Coordinate(12.9716,77.5946),destination=Coordinate(12.9352,77.6245),alternatives=True)).routes))"

# Detector/OpenCV evidence
.\.venv\Scripts\python.exe scripts\verify_yolo_opencv.py

# RDD2022 audit + duplicate scan (read-only)
.\.venv\Scripts\python.exe scripts\audit\phase20_rdd2022_audit.py
.\.venv\Scripts\python.exe scripts\audit\phase20_duplicate_scan.py

# Run the app (UI + API)
.\.venv\Scripts\python.exe scripts\run_app.py
```

## 13. Final verdict

**Functional MVP / advanced prototype — NOT production-ready.**

Reasons: the deterministic core, API, UI, persistence and honesty controls work
and are tested, but (a) **B1/B2** can silently drop hazards and show 100 for an
unassessed-quality result; (b) the detector is **low-accuracy**; (c) **live
imagery and LLM are not enabled/verified** and the imagery fallback is a demo
placeholder; (d) there is **no authentication, rate limiting or CI/CD**. These
must be resolved and re-verified before any production or safety claim.







