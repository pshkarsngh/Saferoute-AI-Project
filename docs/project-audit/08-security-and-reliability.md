# 08 — Security and Reliability

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Related:** [`07-api-database-and-integrations.md`](07-api-database-and-integrations.md) ·
> [`14-findings-and-recommendations.md`](14-findings-and-recommendations.md)

---

## 1. Secret handling

### 1.1 The mechanism

| Rule | Implementation |
|---|---|
| Rule 13 — never commit secrets | `.env` is listed in `.gitignore`; `.env.example` is tracked and contains **variable names with placeholder values only** |
| Rule 13 — local environment configuration | `src/config/env.py` loads `.env` from the workspace root; `get_env` / `get_bool` / `get_int` / `get_float` are the only accessors |
| Rule 13 — no secrets in code | No API key literal appears in any `src/**` file, `config/**` file or `scripts/**` file |
| Rule 13 — no secrets in logs | `http.server`'s default request logging is disabled via `log_message`; the startup banner prints `mapillary_token=yes|no`, never the token |
| Rule 17 — safe config surface | `Settings.to_safe_dict()` is the only outward-facing config method and it never emits secret values |

### 1.2 Credential inventory — by path and type only

**No credential value is reproduced in this document.** The following is a description of
*where credentials live and what kind of credential they are*, per Rule 13.

| Location | Type | Notes |
|---|---|---|
| `.env` (workspace root) | Mapillary access token; Ollama settings | **Gitignored.** 80 bytes. |
| `frontend/Frontend/project frontend/.env` | Frontend public config (`VITE_API_URL` and similar) | **Gitignored.** Contains only public, build-time values by Vite design. |
| `frontend/Frontend/project frontend/.env.example` | Documented variable **names** | Tracked and safe to reference. |
| `.env.example` (workspace root) | Documented variable **names** | Tracked and safe to reference. |
| `config/*.yaml` | **No credentials.** | Every YAML carries an explicit `secrets_file: ".env"` pointer and a comment that secrets never live in config. |

**Observation.** `VITE_*` variables are embedded into the built JavaScript bundle at
build time and are therefore **public by construction**. The frontend `.env.example`
must never contain anything sensitive, and does not. The `VITE_OVERPASS_URL` variable
was removed during Phase 2 because the browser no longer queries Overpass.

### 1.3 The `.env.example` contract

Both `.env.example` files document variable **names** and their purpose. That is the
correct pattern under Rule 13: a new contributor copies the template, fills in real
values locally, and the template itself carries no secret.

## 2. Input validation

### 2.1 What is validated

| Layer | Mechanism |
|---|---|
| JSON body | `_read_json()` reads exactly `Content-Length` bytes, decodes UTF-8 and parses with `json.loads`. A parse failure yields `{}` — an empty payload — rather than an exception. |
| Numeric fields | `_optional_float()` coerces a value to `float`, returning `None` on `TypeError`/`ValueError`. **An unusable value silently becomes the default rather than being rejected.** |
| Location resolution | `_resolve_location()` accepts either `{latitude, longitude}` or a place-name query, with a `required` flag. |
| Categories | `payload.get("categories")` is passed through to the facilities service, which validates it against the configured category list. |
| Route polylines | `normalise_polylines()` in `src/facilities/geometry.py` rejects malformed coordinate pairs. |
| `include_road_access` | Explicitly type-checked: `if not isinstance(include_road_access, bool): include_road_access = True`. |
| Static file paths | `_serve_static` / `_serve_spa_index` resolve and then verify containment inside `static_dir`; a path-traversal attempt is refused (Rule 1). |

### 2.2 What is not validated

| Gap | Assessment |
|---|---|
| No request-body size limit | `Content-Length` is trusted and read in full. A very large body would be buffered into memory. **F-12** |
| No coordinate range check | Latitude beyond ±90 or longitude beyond ±180 is not rejected at the API boundary. |
| No string-length bounds | Origin/destination strings are not length-limited (TRD §15 calls for "types, ranges, string bounds"). |
| No authentication | Every endpoint is open. |
| No rate limiting | Every client may issue unlimited requests; the only throttles are the *provider-side* ones (Nominatim 1 req/s, Overpass 0.7 s gap). |

**Honest assessment.** Input validation is *adequate for a local single-user demo* and
**not adequate for a shared or internet-facing deployment**. The validation style is
also internally inconsistent: some malformed values are rejected with a 400, while others
are silently coerced to a default. That inconsistency is worth fixing before any
deployment, because silently coercing a bad radius or coordinate produces a *plausible
but wrong* answer rather than an error.

## 3. Error handling and information disclosure

### 3.1 The error envelope

```json
{ "status": "failed", "error": { "code": "...", "message": "...", "detail": "..." } }
```

| Code | HTTP | Meaning |
|---|---:|---|
| `invalid_request` | 400 | The request could not be interpreted. |
| `not_found` | 404 | Unknown path, or unknown analysis id. |
| `internal_error` | 500 | Unhandled exception. |

### 3.2 The `detail` field

For `internal_error`, `detail` is set to `f"{type(e).__name__}: {e}"` — the exception type
and message. In the current code paths these are provider or filesystem errors, and no
secret has been observed to reach this field. **However**, an exception message could in
principle contain a filesystem path or an internal structure. For a public deployment,
`detail` should be logged server-side and omitted from the response body.

**F-12** covers this together with authentication and rate limiting.

### 3.3 Failure honesty — the project's strongest security property

The security posture of this project is best described by what it refuses to do:

| Situation | What the system does | What it refuses to do |
|---|---|---|
| Routing provider fails | Returns an explicit routing status with limitations | Never synthesises replacement routes to fill a quota (Rule 10) |
| Mapillary returns 401/403 | `INACCESSIBLE` status for that segment | Never substitutes unrelated sample imagery (PHASE_23B fix) |
| No imagery in the buffer | `UNMATCHED` → segment `unassessed` | Never treats the gap as a clean road (Rule 9) |
| Capture date unknown | Treated as **stale** | Never assumes freshness it cannot verify (Rule 9) |
| Image fails validation | Explicit status (`empty` / `unreadable` / `corrupt` / …) | Never passes a bad image downstream as clean |
| Overpass unreachable | `provider_error` with explanatory notes | Never rewrites the failure as "no hospitals exist" (Rule 20) |
| Road access unavailable | `road_travel_time` stated as unavailable | Never estimates a road distance locally |
| OSM attributes | Echoed verbatim with `attributes_verified: false` | Never promotes a tag into a claim about beds, staffing or opening status (Rule 20) |
| Insufficient coverage | Score suppressed; `unassessed_score_placeholder: null` | Never assigns 100 to an unassessed road (Rule 9) |
| Top scores tied | No recommendation issued | Never fabricates a preference (Rule 14) |
| Demo imagery in play | Excluded from the real-world recommendation | Never presents demo data as live evidence (Rules 9, 20) |
| LLM unavailable / ungrounded | Deterministic `_fallback`, `source: "fallback"` | Never lets free text become a fact (Rule 12) |
| Checkpoint missing | Explicit failure status | Never silently loads a different model |

This is the material distinction between the project and a typical demo: **the failure
modes are the designed part of the product.**

### 3.4 The one silent-degradation risk

The PHASE_28 incident (see [`06-ml-models-and-algorithms.md`](06-ml-models-and-algorithms.md) §8.3)
showed that a *silent* degradation — `source="fallback"` on every request — can persist
without anyone noticing. The fallback is correct behaviour, but there is **no counter, log
line or metric** that surfaces how often it fires. Recommend a log line or counter on
fallback usage.

## 4. Reliability

### 4.1 Concurrency

`ThreadingHTTPServer` serves each request on its own thread (commit `6efc663`,
*"fix(api): use ThreadingHTTPServer for concurrent request handling"*). The imagery
acquisition stage additionally uses a `ThreadPoolExecutor` to prefetch imagery for
segments in parallel (`src/api/pipeline.py`).

**Thread-safety observations.**

| Component | Assessment |
|---|---|
| `AnalysisStore` | Opens a **new `sqlite3` connection per operation** and closes it in a `finally` block. SQLite connections are not shared across threads, so this is the correct pattern and avoids cross-thread connection use. |
| OSRM response cache | An in-process dict with a 120 s TTL, mutated from multiple request threads. **No lock is visible.** Under concurrent writes to a plain dict, CPython's GIL makes individual dict operations atomic, so a corrupt state is unlikely, but a race in the expiry logic is possible. Low severity; worth a lock if the cache grows. |
| Nominatim pacing | A process-wide minimum interval with a lock-protected timestamp — correct for concurrent callers. |
| `AnalysisStore.save_analysis` | Multiple `INSERT`s inside one explicit transaction, committed once. Correct. |

### 4.2 Timeouts and retries

| Call | Timeout | Retries | Backoff |
|---|---:|---:|---:|
| OSRM | 5.0 s (`config/routing.yaml`) | 3 | 0.5 s |
| Overpass | 10.0 s | 2 | 0.5 s |
| Overpass overall | 45.0 s budget across all categories | — | — |
| Nominatim | (see `config/geocoding.yaml`) | bounded | — |
| Ollama | (see `config/app.yaml` → `app.llm.timeout_seconds`) | - | - |
| Browser → `/api/analyze` | 900 000 ms (15 min) | — | — |
| Browser → `/api/routes` | 60 000 ms | — | — |
| Browser → `/api/facilities` | 90 000 ms | — | — |

Every external call is bounded. There is **no unbounded network call** in the backend.

### 4.3 Circuit-breaking behaviour

| Provider | Behaviour under sustained failure |
|---|---|
| Overpass | 3 mirrors tried in turn; the 45 s deadline stops further category queries; the partial result is disclosed |
| OSRM | 3 bounded retries, then an explicit routing failure |
| Mapillary | Explicit status per segment; the pipeline continues with the remaining segments |
| Nominatim | Bounded retries, then an explicit geocode failure |
| Ollama | Deterministic fallback; the analysis still completes |

**No provider's failure aborts the whole analysis.** This is what allows the system to
return a partially-assessed result — which is exactly what Rule 9 wants.

### 4.4 Resource limits

| Limit | Value | Where |
|---|---:|---|
| Images per segment | 3 | `config/imagery.yaml` `matching.max_images_per_segment` |
| Segmentation length | 50–500 m, target 200 m | `config/routing.yaml` `segmentation` |
| Overpass categories per request | 6 configured categories | `config/facilities.yaml` |
| Overpass results per category | 10 | `config/facilities.yaml` `search.max_results_per_category` |
| Road-access requests | 6 per lookup | `config/facilities.yaml` `road_access.max_requests` |
| Detection cap | `max_det: 300` | `config/detection.yaml` |
| LLM prompt | bounded representative sample | `src/llm/explainer.py` (Phase 28) |
| Inference batch | 1 | `config/detection.yaml` |

**Not present:** no request-body size cap, no concurrency cap on analyses, no per-client
budget. TRD §11 and `docs/ARCHITECTURE.md` §11 both call for rate limits and resource
caps; they are implemented at the *provider* level but not at the *client* level.

## 5. Reliability of the honesty guarantees — test coverage

The guarantees in §3.3 are not merely documented; they are asserted by tests.

| Guarantee | Test file | Methods |
|---|---|---:|
| Unassessed ≠ safe | `tests/unit/test_risk_engine.py` | 12 |
| Recommendation correctness (ties, demo, stale, insufficient) | `tests/unit/test_route_recommendation_correctness.py` | 15 |
| Route comparison policy | `tests/unit/test_route_comparison.py` | 14 |
| No imagery substitution on auth failure | `tests/unit/test_phase23b_imagery_integrity.py` | 21 |
| Fresh/stale regression | `tests/unit/test_stale_fresh_regression.py` | 4 |
| Detection outcome distinctness | `tests/unit/test_detection_outcome.py` | 6 |
| Threshold consistency | `tests/unit/test_threshold_consistency.py` | 4 |
| LLM grounding and fallback | `tests/unit/test_llm_explainer.py` | 37 |
| Parallel imagery correctness | `tests/unit/test_pipeline_parallel_imagery.py` | 10 |
| Multi-route latency | `tests/unit/test_multiple_routes_latency.py` | 13 |

**Total: 299 test methods, all passing** (`Ran 299 tests … OK`, measured during Phase 2;
the suite is unchanged since).

## 6. Network exposure

| Exposure | Status |
|---|---|
| Backend bind address | `127.0.0.1` — loopback only, **not** reachable from the network |
| Vite preview | `127.0.0.1:8123` — loopback only |
| Ollama | `127.0.0.1:11434` — loopback only |
| CORS | `Access-Control-Allow-Origin: *` — permissive, but harmless while everything is loopback-only |
| External egress | OSRM, Mapillary, Overpass, Nominatim, OpenFreeMap — outbound only |
| Google Street View | explicitly disabled in config |

**Conclusion:** the system as configured is **not** exposed to the network. The
authentication and rate-limiting gaps (F-12) become real only if the bind address is
changed to `0.0.0.0`. That is a deliberate, documented gate for the deployment phase.

## 7. Findings specific to this document

| ID | Finding | Severity | Rule |
|---|---|---|---|
| F-12 | No authentication, no rate limiting, no request-body size limit, permissive CORS | **High for non-local deployment** | 13, TRD §15 |
| F-20 | Live analyses cannot reach a recommendation because Mapillary capture timestamps are absent | Medium (functional, correct behaviour) | 9 |
| — | Silent LLM fallback is not counted or logged | Low | 20 |
| — | `detail` in the 500 envelope echoes the exception message | Low | 13 |
| — | Numeric coercion silently defaults rather than rejecting | Low | 15 |
| — | OSRM response cache has no lock | Low | — |
| — | No database migration mechanism | Low | 17 |
| — | No indexes declared on the SQLite schema | Low | — |
| — | No `LICENSE` file for the SafeRoute AI source itself | Low | 15 |

---

*All statements above were verified by reading `src/**`, `config/**`, `.gitignore`,
`.env.example` and the test suite on 2026-10-21. No secret value is reproduced anywhere
in this document.*
