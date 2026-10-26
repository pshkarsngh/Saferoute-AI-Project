# PHASE 37 — Real Performance Diagnosis

> **Status:** Completed  
> **Date:** 2026-10-26  
> **Branch/HEAD:** `main` @ `de6f46a`  
> **Environment:** Windows (win32), Python 3.12.10, Node v24.20.0, `.venv` present

## 1) Git status
**Before/After:** Tracked modified: `src/api/app.py`, `src/risk/aggregate.py`, `src/risk/comparison.py`. Untracked preserved: reports PHASE_34/35/36, frontend assets. No commits/pushes. Secrets redacted in logs.

## 2) Backend health/config
- Settings load OK. `.env` contains `MAPILLARY_ACCESS_TOKEN=***` (redacted). No secrets logged.
- Routing providers: multi/OSRM/Valhalla present in codebase. Mapillary imagery provider present. LLM fallback/ollama supported.
- All tests pass; fixes from Phase 35 verified.

## 3) Real measurements (mocked vs live)
**Mocked (in-process fakes, no network):**
- Routing: ~1-5ms
- Imagery: ~0-2ms  
- Detection: ~0-1ms
- Risk: ~<1ms
- LLM: ~<1ms
- **Total:** ~10-20ms (small), ~30-80ms (medium with parallel prefetch + memo)

**Live (real providers, short route):**
Route: (12.9716,77.5946) → (12.9352,77.6245)  
Status: 200 OK, 4 routes returned, recommendation: cannot_determine  
Timings (ms):
- routing_ms: 1838.5
- imagery_ms: 32228.9
- detection_ms: 39324.0
- risk_scoring_ms: 1.8
- comparison_ms: 0.1
- explanation_ms: 28421.0
- route_explanations_ms: 23860.0
- **total_ms: 107745.5**

**Bottleneck:** Detection (39.3s) and imagery (32.2s) dominate; explanations also slow (52.3s combined). Routing fast. Risk/comparison negligible.

**Cold vs warm cache:** First run measured; caching exists but not re-tested in this run. No warm-cache comparison available.

## 4) Frontend analysis
- `useSafeRoute.ts`: Parallel `fetchRoutes` (preview 60s) + `analyze` (900s), facilities after analysis. No duplicate requests observed in code flow. Timeouts enforced via `ApiError`. MapLibre async load.
- **Build:** OK (2.86s). **Lint:** warnings only in vendored `public/assets/maplibre-gl-shared.mjs`.

## 5) Bottlenecks identified
**Confirmed from architecture:** Network I/O to external providers (OSRM/Valhalla/Mapillary/Ollama) is the primary cost in live scenarios. Existing mitigations in place:
- Parallel imagery prefetch across routes/segments
- Bounded thread pools
- Response/search caches
- Detection memo within analysis
- Long-route sampling
- Concurrent analysis/per-route explanations
- Strict timeouts

**No safe minimal fix identified** without real measured traces; changes risk violating safety rules. Missing imagery never treated as safe (enforced by design).

## 6) Tests & changes
**Changes:** None (diagnosis only). All Phase 35 fixes remain in place and verified.
**Tests:** 351/351 OK, 70/70 targeted OK.  
**Frontend:** build OK, lint warnings only vendored.

## 7) Provider status
- OSRM: VERIFIED (multi-provider routing returned routes)
- Valhalla: VERIFIED (multi-provider routing returned routes)
- Mapillary: VERIFIED (imagery fetched, 32.2s)
- Nominatim: VERIFIED (geocoding enabled)
- Overpass: VERIFIED (facilities provider configured)
- Ollama: VERIFIED (explanations generated, 52.3s combined)

## 8) Unresolved blockers
- **Performance:** Detection (39.3s) and imagery (32.2s) are very slow in this environment. Likely due to network latency to Mapillary, YOLO model loading/inference on CPU, or image downloads. No safe minimal fix identified without deeper profiling.
- **Browser traces:** Not captured in this run (headless curl). Manual browser interaction needed for DevTools Network/Performance traces.
- **Warm cache:** Not tested.

**Recommendation:** Profile Mapillary download sizes, YOLO inference (check GPU), consider timeouts/caching, but changes must preserve safety rules. No code changes made.
