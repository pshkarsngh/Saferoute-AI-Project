# 07 — API, Database and Integrations

> **Workspace:** `D:\New folder (3)` · **Audit date:** 2026-10-21
> **Related:** [`02-architecture-and-data-flow.md`](02-architecture-and-data-flow.md) ·
> [`08-security-and-reliability.md`](08-security-and-reliability.md) ·
> [`01-repository-map.md`](01-repository-map.md)

---

## 1. HTTP server

| Property | Value |
|---|---|
| Implementation | Python standard library `http.server` — `BaseHTTPRequestHandler` + `ThreadingHTTPServer` |
| Entry point | `src/api/app.py::main()` / `create_server(host, port, api, static_dir)` |
| Default bind | `127.0.0.1:8000` (from `Settings.host` / `Settings.port`) |
| Threading | `ThreadingHTTPServer` — one thread per request (commit `6efc663` fixed a concurrency defect) |
| Framework | **None** — FastAPI is not installed and installing it is gated by Rule 19 |
| JSON | `json.dumps` / `json.loads` from the standard library |
| Static hosting | The same process serves `frontend/` and falls back to `index.html` for client-side routes |
| Logging | `log_message` overridden to a no-op — "keep logs quiet & secret-free" |

### 1.1 Request dispatch table

Derived directly from `src/api/app.py` `do_GET` / `do_POST`:

| Method | Path | Handler | Success | Failure |
|---|---|---|---|---|
| `GET` | `/api/health` | `SafeRouteAPI.health()` | 200 | — |
| `GET` | `/api/config` | `SafeRouteAPI.config()` | 200 | — |
| `GET` | `/api/analyze/{analysis_id}` | `SafeRouteAPI.get_analysis()` | 200 | 404 `not_found` |
| `GET` | `/api/analysis/{id}/hazards` | `SafeRouteAPI.hazards()` | 200 | 404 `not_found` |
| `GET` | `/api/analysis/{id}/comparison` | `SafeRouteAPI.comparison()` | 200 | 404 `not_found` |
| `GET` | `/api/analysis/{id}/explanation` | `SafeRouteAPI.explanation()` | 200 | 404 `not_found` |
| `POST` | `/api/routes` | `SafeRouteAPI.routes()` | 200 | 400 `invalid_request` |
| `POST` | `/api/analyze` | `SafeRouteAPI.analyze()` | 200 | 400 `invalid_request` |
| `POST` | `/api/geocode` | `SafeRouteAPI.geocode()` | 200 | 400 `invalid_request` |
| `POST` | `/api/facilities` | `SafeRouteAPI.facilities()` | 200 | 400 `invalid_request` |
| `OPTIONS` | any | `_send(204, {})` | 204 | — |
| `GET` | any non-`/api` path | `_serve_static` → `_serve_spa_index` → 404 | 200/404 | — |

**10 documented endpoints** (8 resource + health + config), plus `OPTIONS` and the static
file surface.

### 1.2 Error schema

```json
{ "status": "failed", "error": { "code": "...", "message": "...", "detail": "..." } }
```

Codes in use: `not_found`, `invalid_request`, `internal_error`. Unhandled exceptions are
caught at the dispatch layer and returned as HTTP 500 with a generic message plus a
`detail` string of the form `"{ExceptionType}: {message}"`.

**Note.** The `detail` field echoes the exception text. For internal errors this could
in principle disclose a path or internal structure. It is not a secret leak in the
current code paths, but it is the kind of field that should be reviewed before any
non-local deployment — see [`08-security-and-reliability.md`](08-security-and-reliability.md) §3.

### 1.3 CORS

Every response carries:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Content-Type
Access-Control-Allow-Methods: GET, POST, OPTIONS
```

`Access-Control-Allow-Origin: *` is appropriate for a local single-origin demo, where the
SPA is served from the same process. It is **not** appropriate for a shared deployment
(F-12).

### 1.4 Static file safety

`_serve_static` resolves the requested path against `static_dir` and then checks
`candidate.relative_to(self.static_dir.resolve())`. A `ValueError` from that call means a
path-traversal attempt and the request is refused. `_serve_spa_index` performs the same
containment check. **Rule 1 is enforced at the HTTP boundary.**

## 2. Endpoint contracts

### 2.1 `GET /api/health`

Reports liveness plus the loaded model version and the active providers. Observed on the
live server:

```
model_version : saferoute-yolo11-v2
routing       : osrm
imagery       : mapillary
facilities    : overpass
geocoding     : nominatim
llm           : ollama
```

### 2.2 `GET /api/config`

A **non-secret capability summary**. `Settings.to_safe_dict()` is the only outward-facing
method and it never emits secrets — the Mapillary token is reported as a boolean
presence (`mapillary_token=yes|no` in the startup banner), never as a value.

### 2.3 `POST /api/routes`

Resolves the destination (via `POST /api/geocode` semantics or explicit coordinates),
calls the routing provider, and returns **exactly** the routes the provider returned.
Route count is never padded (Rule 10).

### 2.4 `POST /api/analyze`

Runs the full pipeline and returns the analysis record including per-route results,
comparison, recommendation and explanation. The record is persisted by
`AnalysisStore.save_analysis()` before the response is returned.

### 2.5 `GET /api/analyze/{analysis_id}` and the three `/api/analysis/{id}/…` sub-resources

All four read from the persisted `analyses.result_json` via
`AnalysisStore.get_analysis()`. They are **read-only projections** of the same stored
record — no recomputation.

| Endpoint | Returns |
|---|---|
| `/api/analyze/{id}` | The full analysis record |
| `/api/analysis/{id}/hazards` | `{analysis_id, hazards_count, hazards[]}` — hazards flattened across routes with `route_id` attached |
| `/api/analysis/{id}/comparison` | `{analysis_id, status, comparison, recommendation}` |
| `/api/analysis/{id}/explanation` | The `ExplanationResult` object |

### 2.6 `POST /api/geocode`

Keyless Nominatim. Honours Nominatim's usage policy: a descriptive `User-Agent` and a
process-wide **minimum 1 request per second** interval, with bounded retries.

### 2.7 `POST /api/facilities` — the Phase 2 consolidation

**This endpoint is the single source of truth for facilities.** Before Phase 2 the
browser queried Overpass directly; that client was deleted and the browser-side request
was verified to be absent in the Phase 2 browser check.

Two request shapes are supported:

```jsonc
// A — circle around one point
{ "location": { "latitude": 22.57, "longitude": 88.36 }, "radius_m": 1000, "categories": ["hospital"] }

// B — corridor around route geometry (what the SafeRoute UI uses)
{ "route": { "polylines": [[[88.35, 22.57], [88.42, 22.57]]] },
  "radius_m": 1000, "categories": ["hospital", "medical"], "include_road_access": true }
```

Shape B routes to `FacilitiesService.get_facilities_near_route(polylines, radius, cats,
include_road_access=..., routing_provider=...)`. Shape A routes to
`get_nearby_facilities(lat, lon, radius, cats)`.

**Honest-status guarantee.** The response always carries the provider's real status. A
provider failure is returned as a provider error with explanatory notes — **never**
rewritten as "no hospitals exist" (Rule 20).

## 3. Database

### 3.1 Engine and rationale

**SQLite**, via the standard-library `sqlite3` module. `src/api/store.py` states the
rationale: SQLite is a stdlib module, so no server and no package install is required
(Rule 19), and the schema mirrors TRD §12 and can be ported to MySQL later.

> **Specification divergence.** `docs/TRD.md` §2 and §12 and `docs/ARCHITECTURE.md` §10
> specify **MySQL**. The implementation uses SQLite. Recorded as part of F-02.

| Property | Value |
|---|---|
| Database file | `data/saferoute.db` (`DEFAULT_DB_REL = Path("data/saferoute.db")`) |
| Connection | `sqlite3.connect(str(self.db_path))` per operation, `row_factory = sqlite3.Row` |
| Schema creation | `AnalysisStore._init_schema()` runs `executescript(_SCHEMA)` with `CREATE TABLE IF NOT EXISTS` — idempotent, no migration tool |
| Directory creation | `self.db_path.parent.mkdir(parents=True, exist_ok=True)` |
| Migrations | **None.** The schema is created once and never altered. Adding a column to an existing database will not happen automatically. |
| Indexes | **None declared.** |

### 3.2 Schema — `_SCHEMA` verbatim

```sql
CREATE TABLE IF NOT EXISTS model_versions (
  id TEXT PRIMARY KEY,
  name TEXT,
  checkpoint_path TEXT,
  trained_at TEXT,
  metrics_json TEXT
);
CREATE TABLE IF NOT EXISTS searches (
  id TEXT PRIMARY KEY,
  origin TEXT,
  destination TEXT,
  provider TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS analyses (
  id TEXT PRIMARY KEY,
  search_id TEXT,
  status TEXT,
  model_version TEXT,
  config_hash TEXT,
  result_json TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS scores (
  id TEXT PRIMARY KEY,
  analysis_id TEXT,
  route_id TEXT,
  model_version TEXT,
  config_hash TEXT,
  route_score REAL,
  coverage_fraction REAL,
  status TEXT,
  computed_at TEXT
);
CREATE TABLE IF NOT EXISTS hazard_detections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  analysis_id TEXT,
  route_id TEXT,
  segment_id TEXT,
  image_id TEXT,
  hazard_class TEXT,
  confidence REAL,
  severity REAL,
  bbox_json TEXT,
  status TEXT
);
```

**5 tables**, matching the TRD §12 entity set in spirit but **not** in full. The TRD
specifies `users`, `routes`, `route_segments`, `imagery_refs` and `analysis_history`;
the implementation stores the route/segment/imagery detail inside `analyses.result_json`
rather than in normalised tables. There is no `users` table — consistent with the
project's decision to store no personal data (Rule 13).

### 3.3 Write behaviour — `save_analysis()`

| Table | Operation | Idempotent |
|---|---|:---:|
| `searches` | `INSERT OR REPLACE` keyed on `id` | ✅ |
| `analyses` | `INSERT OR REPLACE` keyed on `id` | ✅ |
| `scores` | `INSERT OR REPLACE` keyed on `"{analysis_id}:{route_id}"` | ✅ |
| `hazard_detections` | `DELETE WHERE analysis_id=?` then `INSERT` | ✅ (explicit delete-then-insert) |

The delete-then-insert for `hazard_detections` was added in Phase 25 so that re-saving an
analysis does not duplicate its detections.

**Persisted audit trail.** Every row carries `model_version` and `config_hash` where
applicable — the TRD §12 requirement that scores reference a route, a model version and
a configuration hash for reproducibility. `model_versions.checkpoint_path` records the
exact weights used.

### 3.4 Privacy

No personal data is stored. `searches.origin` and `searches.destination` hold the
user-supplied origin/destination strings (`json.dumps`-encoded), which for the UI's use
are place names or coordinates. There is no user identity, no session, no IP address and
no authentication record. This satisfies Rule 13's "prefer no personal data".

## 4. External integrations

### 4.1 Routing — OSRM

| Aspect | Value |
|---|---|
| Module | `src/routing/osrm_adapter.py` — `OSRMRoutingAdapter` |
| Endpoint | `https://router.project-osrm.org` (`config/routing.yaml` → `provider.osrm.base_url`) |
| Profile / geometry | `driving`, `overview: full`, `geometries: geojson`, `alternatives: true`, `steps: true` |
| Timeout / retries | 5.0 s, 3 retries, 0.5 s backoff |
| Caching | 120 s in-process response cache |
| Fallback | `MockRoutingAdapter` — **only** when explicitly configured; synthetic routes are flagged as demo and excluded from real-world recommendations (Rules 9, 20) |
| Segmentation | `RouteSegmenter` — target 200 m, floor 50 m, ceiling 500 m |

### 4.2 Imagery — Mapillary

| Aspect | Value |
|---|---|
| Module | `src/imagery/mapillary_provider.py` — Mapillary Graph API client |
| Credential | `MAPILLARY_ACCESS_TOKEN` from `.env` (never from code or config) |
| Licence | CC-BY-SA 4.0, "(c) Mapillary contributors" |
| Spatial match | `SegmentImageryMatcher`, 25 m perpendicular buffer (`config/imagery.yaml` `matching.search_radius_meters`) |
| Retention | Max 3 images per segment, minimum 1 for a non-empty assessment |
| Freshness | `StalenessEvaluator`, 180-day maximum; **unknown capture time ⇒ stale** |
| Storage | `data/imagery/`, inside the workspace (Rule 1), created if missing |
| Demo guard | `config/imagery.yaml` `demo.enabled: false` — local sample frames are never spatially matched and never presented as evidence |

**Honesty guarantees implemented in the provider:**

- No token → the caller-supplied fallback is used if any, and the substitution is
  **disclosed as a limitation**; with no fallback the segment is explicitly unavailable.
- HTTP 401/403 → an explicit `INACCESSIBLE` result. **Geographically unrelated sample
  imagery is never substituted for a rejected live request** (the PHASE_23B fix).
- No imagery in the buffer → `UNMATCHED`, never treated as a safe road.

### 4.3 Facilities — Overpass

| Aspect | Value |
|---|---|
| Module | `src/facilities/overpass_provider.py` |
| Endpoints | 3 mirrors, `max_endpoints: 3` |
| Query strategy | **One query per category**, `query_gap_seconds: 0.7` between them |
| Overall budget | `query_deadline_seconds: 45.0` — when spent, the remaining categories are not queried and the **partial result is disclosed** |
| Timeout / retries | 10.0 s, 2 retries, 0.5 s backoff |
| Geometry | `src/facilities/geometry.py` — `polylines_bbox()`, `distance_to_polylines_m()`, `normalise_polylines()` |

**Category taxonomy** (`config/facilities.yaml`):

| Category | OSM selectors | Notes |
|---|---|---|
| `hospital` | `amenity=hospital` | |
| `medical` | `amenity=pharmacy`, `amenity=clinic`, `amenity=doctors`, `amenity=dentist`, `amenity=doctors_office` | The granular OSM value is returned as `subtype`; the frontend maps `medical` → `medicalFacility`. |
| `police` | `amenity=police` | |
| `fuel` | `amenity=fuel`, `amenity=fuel_station`, `amenity=petrol_station`, `amenity=charging_station` | |
| `hotel` | `tourism=hotel`, `tourism=motel`, `tourism=hostel`, `tourism=guest_house`, `tourism=bed_and_breakfast`, `tourism=chalet` | |
| `restaurant` | `amenity=restaurant` | |

**Search bounds:** `default_radius_m: 1000.0`, `max_radius_m: 5000.0`,
`max_results_per_category: 10`.

**Road access.** `road_access.enabled: true`, `max_per_category: 1` (nearest facility of
each category), `max_requests: 6`. A road distance / travel time is present **only** when
a **real** routing provider actually returned a road route for that facility. A
synthetic provider (mock / fixture / fake) is never used, and no road figure is ever
estimated locally. Otherwise `road_travel_time` is stated as unavailable.

**Attribute honesty.** OSM tags are echoed verbatim (12 tags, 200 characters per value)
together with `attributes_verified: false` and a standing disclaimer: *"as tagged in
OpenStreetMap; not independently verified."* The system never promotes an OSM tag into a
claim about opening status, emergency capability, beds, staffing or capacity (Rule 20).

### 4.4 Geocoding — Nominatim

| Aspect | Value |
|---|---|
| Module | `src/geocoding/nominatim.py` — `NominatimGeocoder` |
| Endpoint | `https://nominatim.openstreetmap.org` |
| Credential | None — keyless |
| Policy compliance | Descriptive `User-Agent`; process-wide minimum 1 request/second; bounded retries |
| Fallback | `MockGeocoder` (offline fixture) |

### 4.5 LLM — Ollama

| Aspect | Value |
|---|---|
| Module | `src/llm/explainer.py` — `GroundedExplanationService` |
| Endpoint | `http://127.0.0.1:11434` |
| Model | `llama3:latest` (installed; Ollama 0.40.6) |
| Output contract | `explanation`, `referenced_routes`, `referenced_hazards`, `disclosures`, `source` |
| Validation | Schema check + entity-grounding check; ungrounded output is **rejected**, not repaired |
| Fallback | `_fallback()` — deterministic template built only from verified backend data; `source: "fallback"` |

### 4.6 Map tiles — OpenFreeMap

Style URL `https://tiles.openfreemap.org/styles/liberty`, map centre `[77.1025, 28.7041]`,
zoom 12. Frontend-only; the backend never touches tile services.

## 5. Live verification status

### 5.1 Services confirmed running during the audit

| Service | Status |
|---|---|
| SafeRoute API on `127.0.0.1:8000` | Running |
| `vite preview` on `127.0.0.1:8123` | Running |
| Ollama 0.40.6 on `127.0.0.1:11434` (`llama3:latest`) | Running |
| Mapillary token | Present in `.env` (value not read into any document) |
| Overpass mirrors | **All unreachable from this machine** |

### 5.2 Overpass unavailability — environment condition, not a code defect

Every public Overpass mirror failed from this host:

| Mirror | Result |
|---|---|
| `overpass-api.de` | HTTP **502** |
| `overpass.kumi.systems` | 30 s read timeout |
| `overpass.private.coffee` | 30 s read timeout |
| `maps.mail.ru` | 30 s read timeout |
| `overpass.osm.jp` | SSL `CERTIFICATE_VERIFY_FAILED` — hostname mismatch |

**Consequence.** A live `POST /api/facilities` returns `status: provider_error` with
honest explanatory notes. This is exactly the behaviour Rule 20 requires — the failure is
disclosed, **not** converted into an empty result that would read as "no hospitals nearby".

**What this means for the audit:** no real facility record was retrieved end to end from
this machine. The provider **success** path is covered by unit tests with a stubbed
`urlopen` (`tests/unit/test_facilities_service.py`, 36 test methods), and the failure
path is verified live. A reviewer with working Overpass access should re-run the live
lookup to confirm the success path in situ — this is listed as an open verification item
in [`14-findings-and-recommendations.md`](14-findings-and-recommendations.md).

### 5.3 Live analysis outcome

Live analyses currently resolve to `recommendation: null` with status
`cannot_determine`, because Mapillary frames return `captured_at = None` — freshness
cannot be verified, so the imagery is treated as stale (Rule 9) and the assessed-length
fraction stays below the recommendation threshold.

**This is correct behaviour, and it is the honest answer.** It also means the live
product currently cannot issue a route recommendation, which is a material functional
gap (F-20) even though the code is behaving correctly.

## 6. Integration summary

| Integration | Direction | Credential | Licence | Failure behaviour |
|---|---|:---:|---|---|
| OSRM | outbound | none | ODbL | bounded retries → explicit routing status; mock only if explicitly configured |
| Mapillary | outbound | token (`.env`) | CC-BY-SA 4.0 | 401/403 → `inaccessible`; no substitution |
| Overpass | outbound | none | ODbL | mirror failover → `provider_error` with notes |
| Nominatim | outbound | none | ODbL | bounded retries → explicit geocode status |
| Ollama | outbound (localhost) | none | local | deterministic `_fallback` |
| SQLite | internal | file path | — | per-operation connection; `sqlite3` errors propagate as 500 |
| OpenFreeMap | outbound (browser) | none | free tier | map tiles only; no safety impact |

---

*Endpoint paths, handler names, schema SQL, config values and provider behaviour in this
document were read directly from `src/api/app.py`, `src/api/store.py`, `src/facilities/*`,
`src/imagery/*`, `src/geocoding/*`, `src/llm/explainer.py`, `src/routing/*` and
`config/*.yaml` on 2026-10-21. No credential value appears in this document.*
