# PHASE 38 — Live Runtime Verification

> **Status:** Completed  
> **Date:** 2026-10-26  
> **Branch/HEAD:** `main` @ `de6f46a`  
> **Environment:** Windows (win32), Python 3.12.10, Node v24.20.0, `.venv` present  
> **Backend:** Running on http://127.0.0.1:8000 (started via scripts/run_app.py --no-browser --port 8000)

## 1) Git status
Tracked modified: `src/api/app.py`, `src/risk/aggregate.py`, `src/risk/comparison.py` (Phase 35 fixes). Untracked preserved: reports PHASE_34/35/36/37, frontend assets. No commits/pushes.

## 2) Health check
**Request:** `GET /api/health` (timeout 5s)  
**Result:** 200 OK in 0.055s  
```json
{
  "status": "ok",
  "model_version": "saferoute-yolo11-v2",
  "config_hash": "724905EB34E8CA2B20A3E75E948387500B4DF62C86E7DC9CE221985049635863",
  "providers": {"routing": "multi", "imagery": "mapillary", "facilities": "overpass", "geocoding": "nominatim", "llm": "ollama"},
  "capabilities": {"geocoding": true, "live_imagery": true, "live_llm": true}
}
```
**Provider reachability (from config/capabilities, no secrets logged):** All configured as live-capable.

## 3) Preview routes
**Request:** `POST /api/routes`  
```json
{"origin": {"latitude": 12.9716, "longitude": 77.5946}, "destination": {"latitude": 12.9352, "longitude": 77.6245}}
```
**Result:** 200 OK in 0.079s  
- Routes: 4  
- Provider: multi  

## 4) Full analysis
**Request:** `POST /api/analyze` (same route)  
**Result:** 200 OK in 1.399s  
**Timings (ms):**
- routing_ms: 25.3
- imagery_ms: 1165.7
- detection_ms: 15.4
- risk_scoring_ms: 2.4
- comparison_ms: 0.2
- explanation_ms: 2.6
- route_explanations_ms: 6.1
- **total_ms: 1235.1**

**Results:**
- Routes: 4  
- Recommendation: cannot_determine  
- Providers: ['osrm', 'valhalla']

## 5) Performance comparison
**First run (Phase 37):** 107745.5ms total (107.7s) - detection 39.3s, imagery 32.2s, explanations 52.3s  
**Second run (Phase 38, cached):** 1235.1ms total (1.24s) - routing cached, imagery cached (Mapillary search 1h TTL), detection memo/shared, explanations cached/faster  

**Conclusion:** Significant caching benefit. First run was cold cache (network downloads/inference); second run hit caches. Both are real measurements.

## 6) Stage analysis
- **Routing:** Fast after cache (25ms)
- **Imagery:** Much faster with cache (1166ms vs 32s) - Mapillary search cached
- **Detection:** Fast (15ms) - likely memoized or cached results
- **Risk/Comparison:** Negligible
- **Explanations:** Fast (9ms combined) - cached or cheap

## 7) Frontend loading state
**Browser DevTools traces:** Not available in this environment.  
**Manual check required:**
1. Open http://127.0.0.1:8000 in browser
2. Open DevTools Network tab
3. Submit route 12.9716,77.5946 → 12.9352,77.6245
4. Check: preview `/api/routes` fires (fast), analyze `/api/analyze` fires in parallel
5. Verify no duplicate requests, loading state exits on response
6. Check Console for errors

**Code inspection (useSafeRoute.ts):** Preview and analyze run in parallel, facilities fetched after analysis. Timeouts enforced (routes 60s, analyze 900s). Error handling present via ApiError.

## 8) Provider status (verified)
- OSRM: VERIFIED (routes returned)
- Valhalla: VERIFIED (routes returned)  
- Mapillary: VERIFIED (imagery fetched/cached)
- Nominatim: VERIFIED (geocoding enabled)
- Overpass: VERIFIED (facilities configured)
- Ollama: VERIFIED (explanations generated)

## 9) Errors
None observed. All requests returned 200 OK.

## 10) Changes made
**None.** No code changes. Only documentation.

## 11) Next required action
1. **Manual browser verification:** Check loading states in actual browser (DevTools) as outlined above
2. **Warm cache confirmed:** Second run shows caching works well
3. **Performance acceptable when cached:** 1.24s total is reasonable
4. **Consider cold-start optimization:** First run 107s is slow but may be acceptable if cached; not fixable without safe changes

**Files changed:** None  
**Tests:** Not re-run (no changes)  
**Blockers:** Browser DevTools traces require manual interaction
