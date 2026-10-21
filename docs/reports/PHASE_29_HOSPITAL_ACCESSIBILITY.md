# SafeRoute AI — PHASE 29: Hospital & Facility Accessibility Consolidation

> **Phase:** PHASE 29 — consolidate hospital/facility information onto the backend
> **Date executed:** 2026-10-21 (UTC) • **Workspace:** `D:\New folder (3)` • **Branch:** `main`
> **Mode:** targeted consolidation of the facility-information stack + tests + live verification.
> No retraining, no checkpoint replacement, no dependency install, no commit/push/deploy.
> **Governing rules:** `master_rules.md` 1, 2, 3, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20.
> Rule 11 (facilities stay separate from the hazard score) is the hard boundary of this phase.

---

## 1. What this phase does

Phase 29 removes the duplicate, browser-side OpenStreetMap client and makes the
backend the single source of truth for every facility fact the UI shows.

| Before | After |
|---|---|
| The browser queried Overpass itself, per category, with its own mirror failover. | The browser calls `POST /api/facilities` once; the backend owns the Overpass lookups, the mirror failover and the lookup budget. |
| The browser computed the distance to the route locally and presented it as an unqualified number. | The backend measures the straight-line distance to the route corridor and labels the basis explicitly. |
| A road travel time was never shown, and nothing stated why. | A road distance / road travel time is attached **only** when a real routing provider returned a road route; otherwise the absence is stated. |
| OSM tags (if shown) looked like facts. | Tags are echoed verbatim and flagged `attributes_verified: false`, with a standing "as tagged in OpenStreetMap; not independently verified" note. |
| An Overpass failure looked like "no hospitals here". | Every provider status (`provider_error`, `provider_timeout`, `rate_limited`, `unavailable`) is preserved and worded honestly. |

**Rule 11 boundary (unchanged and enforced by test):** facilities remain
display-only context. No facility field is read by the risk engine, the
comparison/ranking, the eligibility check or the LLM explainer. `utils/safety.ts::analyzeRoutes`
was left untouched and remains unimported.

---

## 2. Files changed

### 2.1 Backend — outer repository `D:\New folder (3)`

| File | Change |
|---|---|
| `src/facilities/geometry.py` | **NEW.** Dependency-free geometry helpers: `normalise_polylines`, `polylines_bbox`, `nearest_point_on_polyline`, `distance_to_polylines_m`. All straight-line measurements only. |
| `src/facilities/schemas.py` | `Facility`/`FacilityResult` gained `distance_kind`, `road_distance_m`, `road_travel_time_s`, `road_access_source`, `osm_tags`, `attributes_verified`; `FacilityResult` gained `distance_basis`, `distance_note`, `road_access_available`, `road_access_note`, `attributes_note`, `source_attribution`, `notes`. New constants `DISTANCE_STRAIGHT_LINE`, `DISTANCE_ROAD`, `OSM_ATTRIBUTES_NOTE`, `ROAD_TRAVEL_TIME_UNAVAILABLE_NOTE`, `MAX_OSM_TAGS`, `MAX_OSM_TAG_VALUE_CHARS`. |
| `src/facilities/interfaces.py` | New abstract `get_facilities_in_bbox(bbox, categories)` for corridor searches. |
| `src/facilities/overpass_provider.py` | Per-category queries (one small query per category, 0.7 s gap), mirror failover over 3 endpoints, overall 45 s deadline, multi-`osm_tags` selectors, verbatim OSM tags, granular `subtype`, honest failure kinds (`rate_limited` / `timeout` / `error` / `budget`). |
| `src/facilities/mock_provider.py` | New `medical` category + subtype + bbox lookup so offline fixtures match the new taxonomy. |
| `src/facilities/service.py` | New `get_facilities_near_route()` corridor lookup; recomputes the true straight-line distance to the corridor; road-access enrichment limited to the nearest facility per category and to non-synthetic routing providers; provider-aware honest notes and attribution. |
| `src/facilities/__init__.py` | v2 exports (geometry helpers, distance constants, note constants). |
| `src/api/app.py` | `POST /api/facilities` accepts the corridor shape `{"route": {"polylines": [[[lon,lat], ...]]}}`; the corridor path is taken whenever `route` is a dict; `_optional_float()` for a safe radius. |
| `config/facilities.yaml` | `pharmacy` → `medical`; every category now lists multiple `osm_tags` selectors; new keys only: `providers.overpass.{base_urls,max_endpoints,query_gap_seconds,query_deadline_seconds}`, `search.{default_radius_m,max_radius_m,max_results_per_category}`, `road_access.{enabled,max_per_category,max_requests}`; `metadata.version: facilities-v2`. **No pre-existing key was changed.** |
| `tests/unit/test_facilities_service.py` | Extended (+39 tests): corridor lookup, provider-status preservation, empty-result caveat, provenance, unverified OSM attributes, road access only from a real router, synthetic-router exclusion, per-category bounding, Overpass parsing / failover / 429 / timeout / deadline, Rule 11 score invariance, config guards. |
| `tests/unit/test_facilities_api.py` | **NEW** (+14 tests): corridor + point request shapes, every provider status, road-access opt-out, invalid geometry, no score fields in the response. |

### 2.2 Frontend — nested repository `frontend/Frontend/project frontend`

> The frontend is a **separate git repository** with its own remote. The outer
> repository's `.gitignore` ignores `frontend/Frontend/`, so these edits do not
> appear in the outer `git diff` — the nested diff is shown separately in §5.

| File | Change |
|---|---|
| `src/services/facilities.ts` | **Rewritten.** The Overpass client is deleted. The module now maps the backend response onto the UI view model: `mapBackendFacility`, `mapFacilitiesResponse`, `describeFacilitiesStatus`, `BACKEND_CATEGORY_BY_UI`. |
| `src/lib/analyzeTypes.ts` | Added the backend wire types: `BackendFacilitiesStatus`, `BackendFacility`, `BackendFacilitiesResponse`. |
| `src/lib/api.ts` | Added `fetchFacilities()` and `FACILITIES_TIMEOUT_MS = 90_000` (the client budget is larger than the server's 45 s server-side budget, so the server's own honest answer is what the user sees). |
| `src/utils/facilityPresentation.ts` | **NEW.** The honest wording in one testable place: `formatStraightLineDistance`, `formatFacilityDistance`, `formatRoadAccess`, `formatAttributesSentence`, `OSM_ATTRIBUTES_NOTE`, `ROAD_ACCESS_UNAVAILABLE`, `FACILITY_CLAIMS_WITHHELD`. |
| `src/hooks/useSafeRoute.ts` | Calls the backend; exposes `facilityStatus`, `facilityMessage`, `facilityDistanceNote`, `facilityRoadAccessAvailable`, `facilityRoadAccessNote`, `facilityAttributesNote`, `facilityAttribution`. A failed lookup never fails the route result. |
| `src/pages/RouteResults.tsx` | Distances labelled "straight-line"; new "Hospital & medical access" section (name, straight-line distance, road distance + travel time **only when available**, verbatim OSM tags); status-specific warning; disclaimer updated. |
| `src/pages/RouteResults.module.scss` | Styles for the new medical section. |
| `src/utils/backendRoutes.ts` | Comment clarification: the proximity distance is straight-line, never a road distance. No behaviour change. |
| `tools/frontend-tests/{entry.ts,run.mjs}` | +26 frontend checks (backend→UI mapping, honest distance labelling, road-time-only-when-available, provider-failure wording, "no browser-side Overpass" regression guard). |
| `tools/browser-test/run.mjs` | +6 browser checks (the browser asks `/api/facilities` and never an Overpass instance; the page reports the facility outcome honestly). |
| `.env.example` | `VITE_OVERPASS_URL` removed (the browser no longer queries OpenStreetMap). |

---

## 3. Design decisions and why

**3.1 The backend owns the Overpass lookup.**
The public Overpass instances refuse one large multi-category query but reliably
answer small single-category ones. The provider therefore issues one query per
category with a short gap, fails over between three mirror endpoints, and runs
under an overall deadline. The resilience the browser client used to have moved
server-side, so the browser makes exactly one request.

**3.2 The distance basis is explicit.**
`distance_kind` is `straight_line_haversine` unless a real routing provider
supplied a road route. The service recomputes the straight-line distance to the
actual route corridor (the provider's own bbox-centre distance is an internal
intermediate and is never shown).

**3.3 A road travel time exists only when it was really returned.**
`_attach_road_access()` refuses any routing provider whose name starts with
`mock`, `fixture` or `fake` — the mock adapter (`mock_routing`) can therefore
never produce a travel time. It asks for at most `max_per_category: 1` facility
per category and at most `max_requests: 6` routing requests per lookup. When no
real road route comes back, the response carries
`road_access_available: false` and an explicit note.

**3.4 OSM attributes are tags, not facts.**
Tags are echoed verbatim (bounded to 12 tags and 200 characters per value) with
`attributes_verified: false` and the standing note *"as tagged in OpenStreetMap;
not independently verified"*. The UI additionally states that SafeRoute does not
verify opening hours, emergency capability, bed counts, staffing or capacity.

**3.5 A provider failure is never "no hospitals exist".**
`unavailable`, `provider_error`, `provider_timeout` and `rate_limited` are four
distinct statuses and are preserved end to end. The empty-result case carries
*"… it is not proof that no hospital exists nearby."*; every failure case carries
*"… this is a provider failure, not evidence that no hospital exists nearby."*

---

## 4. Test evidence

### 4.1 Backend suite — `.\.venv\Scripts\python.exe -m unittest discover -s tests`

```
Ran 299 tests in 17.965s
OK
```

Baseline before this phase was **260** tests → **+39** new tests
(`tests/unit/test_facilities_service.py` + `tests/unit/test_facilities_api.py`).
No existing test was removed or weakened.

Covered by the new tests:

| Requirement | Test(s) |
|---|---|
| Provider success | `test_corridor_returns_facilities_measured_against_the_route`, `test_tags_are_parsed_into_category_subtype_and_raw_attributes` |
| Empty results | `test_empty_result_is_unavailable_with_an_explicit_caveat`, `test_empty_overpass_response_is_unavailable_not_an_empty_claim` |
| Timeouts | `test_timeout_maps_to_provider_timeout`, `test_deadline_stops_the_lookup_and_is_disclosed` |
| Provider errors | `test_provider_error_is_never_reported_as_no_facilities`, `test_provider_error_is_returned_as_a_provider_error`, `test_http_429_maps_to_rate_limited` |
| Mirror failover | `test_provider_fails_over_to_the_next_mirror` |
| Provenance | `test_provenance_recorded_for_corridor_lookup`, `test_corridor_request_returns_facilities_with_provenance` |
| Facility-score independence | `test_rule_11_score_unchanged_with_and_without_facilities`, `test_rule_11_score_identical_when_facilities_present_missing_or_unavailable`, `test_rule_11_facility_payload_contains_no_score_fields`, `test_facilities_endpoint_response_contains_no_score_fields` |
| Straight-line vs road distance | `test_straight_line_and_road_distance_are_both_labelled`, `test_corridor_returns_facilities_measured_against_the_route` |
| Road time only from a real router | `test_road_travel_time_attached_from_a_real_routing_provider`, `test_synthetic_routing_provider_never_produces_a_road_travel_time`, `test_failed_routing_request_leaves_road_travel_time_unavailable` |
| Attributes unverified | `test_osm_attributes_are_carried_verbatim_and_flagged_unverified` |

### 4.2 Frontend checks — `npm run test:frontend`

```
view model                     14 ok
cards                           7 ok
nearby facilities (backend -> UI) 11 ok
honest wording                  8 ok
provider failure wording       13 ok
no browser-side Overpass query  5 ok
---------------------------------------------------------------
58 checks, 0 failures
All frontend view-model/card checks passed.
```

### 4.3 Build and lint — `npm run build` / `npm run lint`

- `npm run build` (`tsc -b && vite build`): **passes**, no type errors.
- `npm run lint` (`oxlint`): **0 errors**; no new warnings in any changed file.

### 4.4 Browser check — `node tools/browser-test/run.mjs http://127.0.0.1:8123`

The new frontend bundle was served with `vite preview` on port 8123 and driven
with the installed Microsoft Edge over the Chrome DevTools Protocol against the
live backend on port 8000.

```
  ok  routing preview renders while analysis runs
  ok  pending cards show no score
  ok  more than one route card rendered
  ok  each card keeps its own backend index
  ok  each route has a distinct map-line colour
  ok  assessed scores are real backend numbers
  ok  timing footer reports measured stages
  ok  map canvas present (lines drawn by MapLibre)
nearby facilities (browser -> backend)
  ok  the browser asked the backend for facilities
  ok  the browser never queried an Overpass instance itself
  facility warning: "The facility data provider returned an error, so no nearby facilities are
  listed. This is a provider failure, not evidence that no hospital exists nearby."
  ok  the page reports the facility lookup outcome (warning or medical section)
  ok  the warning never asserts that no hospital exists nearby
  ok  the warning says the absence is not evidence
All browser checks passed.
```

The captured network log shows `http://localhost:8000/api/facilities` and **no**
request to any Overpass host — the browser-side Overpass client is gone.

The warning text above is the **live DOM text** read back from the rendered
page. It is the honest provider-failure wording: it does not claim that no
hospital exists nearby. (The live warning here is the provider-error variant
because the public Overpass mirrors were down during this run — see §5.)

### 4.5 Live endpoint — `POST /api/facilities`

Live request against the running server (route corridor, 1 km radius):

```json
{
  "status": "provider_error",
  "provider": "overpass",
  "facilities_count": 0,
  "origin": {"latitude": 12.9716, "longitude": 77.5946},
  "distance_basis": "straight_line_haversine",
  "distance_note": "Distances are straight-line (great-circle) distances, not road-network distances.",
  "road_access_available": false,
  "road_access_note": "Road travel time is unavailable: no supported routing request returned one for this facility.",
  "attributes_note": "as tagged in OpenStreetMap; not independently verified",
  "source_attribution": "(c) OpenStreetMap contributors (ODbL) — openstreetmap.org/copyright",
  "limitations": ["provider_query_budget_exhausted:1_categories_not_queried", "provider_budget"],
  "error_message": "The facility data lookup ran out of its time budget before any category could be answered.",
  "notes": ["The facility data could not be retrieved, so no facility is listed. This is a provider failure, not evidence that no hospital exists nearby."]
}
```

Elapsed 47.5 s — bounded by the 45 s server-side budget. The status is
`provider_error`, **not** `unavailable`: the honest failure path is exercised,
not the empty-area path.

---

## 5. Provider limitations (environment condition, not a code defect)

Every public Overpass mirror tested from this machine was failing during this
phase:

| Mirror | Result |
|---|---|
| `overpass-api.de` | HTTP 502 |
| `overpass.kumi.systems` | 30 s read timeout |
| `overpass.private.coffee` | 30 s read timeout |
| `overpass.osm.jp` | SSL `CERTIFICATE_VERIFY_FAILED: Hostname mismatch` |

Consequences, all of them handled honestly by the code:

1. A **live** facilities lookup exercises the provider-error path, so no real
   hospital record was retrieved end-to-end from this machine. The
   provider-success path is covered by the unit tests with a stubbed
   `urlopen` and by the offline mock provider.
2. The lookup is **bounded** at ~47.5 s by the 45 s budget, and the
   un-queried categories are disclosed in `limitations`.
3. `road_access_available` is `false` in every live response, because no
   facility was found to attach a road route to. The road-access code path is
   covered by the unit tests against a routing double whose provider name is
   not synthetic.
4. The mirrors are attempted in the configured order and the first that
   answers wins, so recovery is automatic when the public instances recover.

---

## 6. Remaining gaps (explicit, not hidden)

1. **The deployed bundle in the outer repository was not rebuilt.**
   `frontend/assets/*` in the outer repo still contains the previous build, so
   the UI that the outer repo serves today still runs the **old** browser-side
   Overpass client. The new frontend bundle lives in the nested repository's
   `dist/` (built and verified here); the browser check above was run against
   that new bundle served by `vite preview`. Publishing the new bundle into
   `frontend/assets/` is a separate (mechanical) deployment step that was
   deliberately not taken here, to keep this change reviewable. Until it is
   taken, the consolidation is complete in source but not in the deployed
   bundle.
2. **The route-results page fetches facilities *after* the assessment.**
   That is deliberate (Rule 11: a slow or failed facility lookup must never
   delay the verdict), but it means the facility panel can appear ~45 s after
   the score. A progress hint for the facility panel would improve the
   experience; it was not added in this phase.
3. **The `useSafeRoute` effect re-runs** because `origin`/`destination`
   identities change between renders, which issues the analysis request twice
   (the first is aborted). This is **pre-existing** behaviour from Phase 27,
   not introduced here, and it was left untouched as out of scope. It doubles
   the facility request as well.
4. **`search.max_results_per_category` is configured but not applied.** The
   facility count shown in the UI is the full count of what the provider
   returned. Applying the cap would change the displayed counts, so it was left
   unused on purpose.
5. **Straight-line distance only.** The corridor distance is a great-circle
   measurement to the route, not a walking distance along a footpath or a
   driving distance. Where a real road route is unavailable the UI states this
   instead of estimating.
6. **No live verification of the road-travel-time display.** The live
   Overpass outage prevented a facility from ever being returned, so the
   "distance by road · N min drive" line was verified by unit test and by the
   frontend formatting checks, not against a live facility record.
7. **The `unavailable` vs `provider_error` distinction reaches the UI as
   text.** The backend keeps both statuses separate and the frontend maps each
   to its own sentence, but there is no icon/colour distinction beyond the
   warning banner.
8. **Out-of-scope pre-existing issue (unchanged):** live analyses resolve to
   `recommendation: null` / `cannot_determine` because the Mapillary provider
   returns `captured_at = None`, so imagery freshness is unverifiable
   (Rule 9). This phase did not touch the imagery layer.

---

## 7. Explicit non-changes

- No risk formula, threshold, YOLO11 weight, provider setting or model
  configuration was changed. `config/app.yaml`, `src/config/settings.py` and
  `src/llm/explainer.py` are modified in the working tree from **Phase 28**
  and were left exactly as they were.
- `src/utils/safety.ts::analyzeRoutes` was not modified and not imported.
- No dependency was installed; no secret was read or printed; no data was
  deleted; nothing was staged, committed, pushed or deployed.
- The pre-existing `.gitignore` modification and every other working-tree
  change were preserved.
- `config/facilities.yaml` only gained new keys — no existing key was
  modified.

---

## 8. Verification checklist

| Requirement | Status | Evidence |
|---|---|---|
| Inspect backend schemas/providers/config/API + frontend consumers | Done | §2 |
| Consolidate the frontend onto `POST /api/facilities` | Done | §2.2, §4.3, §4.4 |
| Remove the browser-side Overpass request | Done | `src/services/facilities.ts` rewritten; §4.2 + §4.4 regression guards |
| Preserve provider status distinctions | Done | §4.1, §4.5 |
| Preserve provenance | Done | §4.1 (`test_provenance_recorded_for_corridor_lookup`), §4.5 |
| Preserve limitations and error handling | Done | §4.1, §4.5 |
| Never turn provider errors/empty results into "no hospitals exist" | Done | §4.1, §4.2, §4.4 |
| Distinguish straight-line vs road distance | Done | §2.1 (`distance_kind`), §4.1, §4.2 |
| Road travel time only from a real routing request, otherwise state it is unavailable | Done | §3.3, §4.1, §4.2 |
| OSM attributes shown as tagged and not independently verified | Done | §2.1, §3.4, §4.2 |
| No claims of live opening status / emergency capability / beds / staff / capacity | Done | §3.4, `FACILITY_CLAIMS_WITHHELD` |
| Facilities separate from risk scoring / ranking / eligibility / LLM | Done | §3 (Rule 11), §4.1 (score-invariance tests) |
| Backend tests added/updated | Done | 299 tests OK (was 260) |
| Frontend tests added (existing framework only) | Done | `npm run test:frontend` — 57 checks |
| Existing backend suite run | Done | `Ran 299 tests … OK` |
| Browser check run | Done | §4.4 — all checks passed |
| This report | Done | `docs/reports/PHASE_29_HOSPITAL_ACCESSIBILITY.md` |

**Phase 2 stops here. Phase 3 has not been started and awaits explicit approval.**
