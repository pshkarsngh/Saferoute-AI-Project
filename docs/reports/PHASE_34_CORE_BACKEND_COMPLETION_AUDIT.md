# PHASE 34 — Core Backend & Pipeline Completion Audit (Phase A Baseline)

> **Status:** Read-only baseline audit. No files modified.  
> **Date:** 2026-10-26  
> **Branch/HEAD:** `main` @ `de6f46a` (feat(pipeline): bound long-route imagery with disclosed evidence budget)  
> **Environment:** Windows (win32), Python 3.12.10, Node v24.20.0, `.venv` present  

## 1) Baseline state

| Item | Value | Notes |
|---|---|---|
| Git status | Clean tracked; 3 untracked frontend assets | `frontend/assets/Loader-DawLJoxi.js`, `dotlottie-state-machine-manager-2E7RUGJG-NTQ25VSR-uJQx0K0V.js`, `index-ByRfyWku.js` (must preserve) |
| Tests | 351 tests, OK (exit code 1 in PS due to stderr) | Log: `$env:TEMP\saferoute_baseline_tests.txt` |
| Backend modules | 52 Python modules, ~9514 lines | `src/` |
| Test files | 27 (`tests/unit/*`, `tests/integration/*`) | Full suite passes |
| Frontend served bundle | `frontend/index.html` references `index-CXsvefbt.js` + `index-BiUo2j2m.css` | Matches `frontend/Frontend/project frontend/dist/assets/` (F-06 appears resolved in current tree; extra untracked assets are stale leftovers) |
| Dead code | `frontend/Frontend/project frontend/src/utils/safety.ts` has no importers | F-07 still present (not imported) |
| Checkpoint | `models/training/saferoute-yolo11-v2/weights/best.pt` exists | Serving model `saferoute-yolo11-v2` (detector) |
| Secrets | `.env` contains `MAPILLARY_ACCESS_TOKEN` | Never serialized by `Settings.to_safe_dict()`; token only in backend |

## 2) Architecture (authoritative)
- **API:** stdlib `http.server` + `ThreadingHTTPServer` (`src/api/app.py`). FastAPI/MySQL not used (Rule 19). This matches actual implementation despite older docs.
- **Persistence:** `sqlite3` (`src/api/store.py`).
- **Scoring:** Deterministic risk engine (`src/risk/engine.py`) is sole score authority (Rule 7). LLM only explains (`src/llm/explainer.py`, schema in `src/llm/schemas.py`).
- **Providers (live):** OSRM routing (fallback/multi), Mapillary imagery (token-gated), Overpass facilities, Nominatim geocoding, Ollama LLM with deterministic fallback. All degrade gracefully and disclose failures.
- **Long-route budget (PHASE_33):** `SafetyAnalysisPipeline` applies sampling when route length > threshold; skipped segments remain in `segment_scores` as unassessed, `assessed_length_fraction` and coverage remain truthful (tested in `tests/unit/test_long_route_budget.py`).

## 3) Pipeline stage verification (read-only)

| Stage | Key files | Expected | Observed/Notes | Tests |
|---|---|---|---|---|
| Input validation | `src/api/app.py` (`_parse_coord`, `_resolve_location`, `analyze/routes/geocode`) | Bad coords/types rejected with 400; ranges/strings validated | `_parse_coord` does `float(...)` with no try/except and no range checks. Passing `{"latitude":"abc"}` raises `ValueError` (uncaught) → would become HTTP 500. `999` is accepted (no range validation). | `tests/unit/test_api.py` covers some negative cases; missing explicit 400 for non-numeric/out-of-range coords. |
| Geocoding | `src/geocoding/*` (nominatim, factory, mock) | Empty/ambiguous/invalid/failed handled; disclosure of resolution source | Implemented with status/results; API discloses `origin_resolution`/`destination_resolution`. | `tests/unit/test_geocoding.py` present. |
| Routing | `src/routing/osrm_adapter.py`, `multi_adapter.py`, schemas | Genuine provider routes only; no padding; dedup without losing distinct alternates; <4 routes allowed | Adapters return provider routes as-is; tests enforce “no padding” (Rule 10). | `tests/unit/test_routing_adapter.py`, `tests/unit/test_multi_routing_adapter.py` pass. |
| Segmentation | `src/routing/segmentation.py` | Configured target/min/max lengths respected | Used by adapters; appears consistent. | Covered indirectly by pipeline tests. |
| Imagery retrieval | `src/imagery/adapter.py`, `mapillary_provider.py`, schemas | Geographically relevant, permitted sources only, permissions respected; missing/stale/insufficient represented honestly; no demo substitution for real requests | Mapillary path exists; staleness/freshness handling present. Live Mapillary may return frames with missing `captured_at` → treated as stale (see F-20 in audit). Demo mode disabled by default. | `tests/unit/test_imagery_adapter.py`, `tests/unit/test_mapillary_provider.py`, `tests/unit/test_phase23b_imagery_integrity.py` pass. |
| Preprocessing | `src/preprocessing/pipeline.py` | Image validation/preprocessing with explicit statuses | Implemented; unsupported extensions handled. | `tests/unit/test_preprocessing.py` passes. |
| YOLO11 inference | `src/detection/detector.py`, schemas | Checkpoint loads; only supported classes used; preprocessing/conf/IO/schema match; failures safe (no false zero-hazard); version/traceable | Loads `saferoute-yolo11-v2/best.pt`; maps unsupported classes to `unsupported_class_{id}` with disclosure (Rule 5). `ImageDetectionResult.status` distinct for no_detections vs success. | `tests/unit/test_detection.py`, `tests/unit/test_detection_outcome.py` pass. |
| Hazard validation/dedup | `src/risk/aggregate.py`, schemas | Confidence filter, spatial dedup, supported classes only contribute as hazards? | Confidence filtering applied. Spatial IoU dedup within image/class. **Issue:** unsupported-class detections from detector become `HazardRecord` with `severity` assigned by `SeverityPolicy` (default base for unsupported is 1.0 in policy) and `status="assessed"` — currently counted as hazards (see defect #3). | `tests/unit/test_hazard_aggregation.py` passes (doesn’t currently test unsupported-class handling). |
| Deterministic risk engine | `src/risk/engine.py`, schemas, config `config/risk_engine.yaml` | Sole authority; scores only from validated detections/eligible segments; coverage/insufficient-evidence enforced; unassessed never gets fabricated score; facilities don’t affect score; LLM can’t change scores | Enforces suppression for insufficient coverage (sets `is_suppressed=True`, keeps computed score) and returns `None` for UNASSESSED/FAILED. Route aggregation length-weighted. `detection_outcome` discloses “no_hazards_detected” vs insufficient coverage vs unassessed. | `tests/unit/test_risk_engine.py` passes (including suppression test). |
| Coverage/assessment status | Engine + pipeline | Truthful coverage; skipped segments remain; partial/insufficient handled | Long-route budget keeps all segments in results with unassessed for skipped; `assessed_length_fraction` computed from segment scores. **Issue:** `assessed_length_fraction` counts any segment with `segment_score is not None` as assessed length — suppressed segments (insufficient coverage) have a computed score and are not marked `is_suppressed` in the “assessed length” sense? Current behavior: suppressed segment yields `segment_score=100.0, is_suppressed=True` but `assessed_length_fraction` counts it (see defect #2). Test `test_rule_9_insufficient_coverage_suppresses_safe_verdict` expects score computed but suppressed; comparison uses `assessed_length_fraction` for eligibility. |
| Route comparison | `src/risk/comparison.py`, `config/route_comparison.yaml` | Deterministic, only over verified scores; demo/stale excluded; insufficient coverage excluded; ties → no recommendation; unassessed never ranked as safe | Implemented with policy; uses `assessed_length_fraction`. | `tests/unit/test_route_comparison.py`, `tests/unit/test_route_recommendation_correctness.py`, `tests/unit/test_stale_fresh_regression.py` pass. |
| Grounded LLM explanation | `src/llm/explainer.py`, schemas | Grounded in backend facts only; no invention of scores/detections; invalid JSON/timeout/unavailable → deterministic fallback with `source="fallback"`; API distinguishes source | Implemented with grounding checks and fallback. | `tests/unit/test_llm_explainer.py` passes. |
| Persistence/API | `src/api/store.py`, `src/api/app.py` | SQLite schema consistent; stable IDs; correct retrieval; safe errors; no secrets; all endpoints work | Endpoints: health, config, geocode, routes, analyze, GET /api/analyze/{id}, /api/analysis/{id}/hazards/comparison/explanation, facilities. All return consistent envelopes. | `tests/unit/test_api.py`, `tests/integration/test_end_to_end_api.py` pass. |
| Frontend integration | `frontend/index.html`, `frontend/Frontend/project frontend/src/lib/api.ts`, hooks/components | Served build is current (`index-CXsvefbt.js`); API base URL configurable; states handled; unassessed not shown as safe; errors visible | `API_URL` defaults to `http://localhost:8000`; analyze timeout 900s. Frontend reads backend fields (route_score, coverage, hazards, explanation). Dead `utils/safety.ts` not used. | Frontend build exists; not rebuilt in this audit (per F-18). |

## 4) Confirmed defects (empirically verified)

### D-01: `_parse_coord` does not validate types/ranges → unhandled ValueError or accepts invalid coords
- **Evidence (probe):**
  - `{"latitude":"abc", "longitude":77.6}` → `RAISED ValueError: could not convert string to float: 'abc'` (uncaught in API path)
  - `latitude=999, longitude=77.6` → accepted, analysis returns `200 assessed`
  - `latitude=12.9, longitude=999` → accepted, analysis returns `200 assessed`
- **Location:** `src/api/app.py:43-48` `_parse_coord` does `float(value[...])` with no try/except; `Coordinate` dataclass has no validation.
- **Impact:** Non-numeric coords can cause 500s (poor error handling); out-of-range coords (|lat|>90, |lon|>180) are accepted and flow through routing/geocoding/analysis (violates basic input validation; TRD §15 expects ranges). Also affects all call sites (`_resolve_location`).
- **Fix (proposed, minimal):** Make `_parse_coord` robust to non-numeric values (catch `TypeError/ValueError`) and validate ranges; return `None` on failure so API returns 400 with `invalid_request`. Also consider validating in `Coordinate` or at API boundary. Update callers/tests as needed.

### D-02: `assessed_length_fraction` counts suppressed segments as assessed length
- **Evidence (probe):**
  - 40%-coverage suppressed segment: `segment_score=100.0`, `is_suppressed=True`, but `assessed_length_fraction=1.0`
- **Location:** `src/risk/comparison.py:79-97` `assessed_length_fraction` counts segments where `s.get("segment_score") is not None`. `src/risk/engine.py:160-177` sets `is_suppressed=True` when coverage < threshold but still returns computed `segment_score`.
- **Impact:** RouteComparer uses `assessed_length_fraction` for eligibility (`_is_sufficiently_assessed` requires fraction >= min). A route with mostly suppressed (insufficient coverage) segments could appear fully assessed and potentially become eligible for recommendation in edge cases, contradicting “insufficient evidence cannot support recommendation” (Rule 9). The test `test_rule_9_insufficient_coverage_suppresses_safe_verdict` expects suppression behavior on the segment; the fix must preserve that test’s intent (don’t null segment_score) but make eligibility truthful.
- **Fix (proposed, minimal):** Change `assessed_length_fraction` to exclude segments where `is_suppressed` is true (and/or where status indicates unassessable). Also consider excluding FAILED/UNASSESSED (already excluded by `segment_score is None`). This aligns with docstring “segments without a score (unassessed/failed/suppressed) contribute zero assessed length”.

### D-03: Unsupported classes become scored hazards (violates Rule 5 honesty)
- **Evidence (probe):**
  - Detection of class `unsupported_class_7` (status `unsupported_class`) becomes `HazardRecord(severity=1.2)`, `aggregate_hazard=1.2`, segment status `assessed`
- **Location:** `src/detection/detector.py:330-353` creates `DetectionRecord` with `hazard_class="unsupported_class_{id}"`, `status="unsupported_class"`. `src/risk/aggregate.py:179-228` processes all detections that pass confidence filter regardless of class/support status; `SeverityPolicy.calculate_severity` likely has a base for unsupported (severity.py:66 shows `self.base_severities.get("unsupported", 1.0)`) and will assign severity. `HazardAggregator.process_detection` creates `HazardRecord` with `status="assessed"`.
- **Impact:** Unsupported/unrecognized classes are treated as real hazards and affect aggregate hazard/route scores, which is dishonest (Rule 5 says “Discloses unsupported classes honestly”). They should be disclosed as limitations/unsupported but not scored as hazards.
- **Fix (proposed, minimal):** In `HazardAggregator.process_detection` (and/or `process_image_detections`), skip detections where `detection.status == "unsupported_class"` or `detection.hazard_class` starts with `unsupported_class` (or not in supported set). Do **not** create `HazardRecord` for them; record them in limitations/disclosures instead. Ensure `aggregate_hazard` unchanged and segment remains assessable only if other valid hazards exist, but unsupported classes must not contribute.

## 5) Proposed fixes (Phase B plan)
1. **D-01 `_parse_coord` hardening**
   - In `src/api/app.py`, change `_parse_coord` to catch `ValueError/TypeError` and validate ranges: `-90 <= lat <= 90`, `-180 <= lon <= 180`. Return `None` if invalid.
   - In `SafeRouteAPI._resolve_location`, when coord parsing fails due to bad types/ranges, return appropriate error (400). Also ensure `geocode/routes/analyze` return 400 with clear messages.
   - Add regression tests for invalid types and out-of-range coords.

2. **D-02 `assessed_length_fraction` exclude suppressed**
   - In `src/risk/comparison.py`, in `assessed_length_fraction`, skip segments where `s.get("is_suppressed")` is truthy (and keep existing behavior for None score/unassessed/failed).
   - Verify `test_rule_9_insufficient_coverage_suppresses_safe_verdict` still passes (segment_score remains computed and suppressed). Update/add tests for eligibility.

3. **D-03 Ignore unsupported classes in aggregation**
   - In `src/risk/aggregate.py`, in `process_detection` and/or `process_image_detections`, skip detections with `status == "unsupported_class"` or unsupported class names. Add to segment limitations that unsupported classes were detected/disclosed. Ensure they don’t affect `aggregate_hazard`.
   - Verify detector still discloses them (it already does). Add regression test.

## 6) Test commands (exact)
```powershell
# Baseline (already run)
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v 2>&1 | Tee-Object -FilePath \"$env:TEMP\\saferoute_baseline_tests.txt\"

# Targeted after fixes
.\\.venv\\Scripts\\python.exe -m unittest tests.unit.test_api tests.unit.test_risk_engine tests.unit.test_route_comparison tests.unit.test_route_recommendation_correctness tests.unit.test_hazard_aggregation -v
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v
```

## 7) Live provider status
- **Mapillary:** Token present in `.env` (`MAPILLARY_ACCESS_TOKEN`). Live path exists in `src/imagery/mapillary_provider.py`. Not exercised in unit tests (mocked). May have missing timestamps → stale (F-20). **Unverified live in this audit.**
- **OSRM/Nominatim/Overpass/Ollama:** Live-capable; tests use mocks/fakes. **Unverified live in this audit.**

## 8) Acceptance criteria readiness
- [x] Every critical pipeline stage documented with files/tests/notes
- [ ] All confirmed critical defects resolved (3 identified, fixes proposed)
- [x] Route alternatives genuine, no padding (tests pass)
- [ ] Ineligible imagery cannot support recommendation (partly addressed by budget/staleness; need to verify after fixes)
- [ ] Detector failures cannot be mistaken for zero hazards (detection_outcome + statuses exist; unsupported classes need fix)
- [x] Risk scores/coverage deterministic and traceable (engine + config hashes)
- [x] Unassessed never labeled safe (enforced)
- [x] LLM grounded with fallback
- [x] DB/API contracts pass (351 tests OK)
- [ ] Frontend uses intended build and represents states correctly (build exists; needs verification)
- [ ] Full regression passes after fixes (currently passes baseline)
- [x] External integrations marked unverified where not tested live

**Overall:** Baseline is solid (351/351 passing). Three concrete defects identified with minimal fixes proposed. Ready to proceed to Phase B.
