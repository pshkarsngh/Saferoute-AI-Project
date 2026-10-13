# PHASE_13 — Routing Adapter Report

=================================
**Date (actual):** 2026-10-13  
**Phase ID:** PHASE_13  
**Governing Documents:** TRD §10, ARCHITECTURE §8, master_rules.md Rules 8, 10, 13, 14  

---

## 1. Provider Selection

- **Chosen Provider (Live):** **Open Source Routing Machine (OSRM) / OpenStreetMap (OSM)**
- **Chosen Provider (Test / Offline):** **MockRoutingAdapter (`mock_routing`)**
- **Alternatives Evaluated:**
  - *OSRM / OpenStreetMap:* Open Database License (ODbL) / BSD license, $0 cost, global coverage, no paid API keys required for public demo or local self-hosted instances, supports multi-route alternatives (`alternatives=true`), GeoJSON geometries, road maneuver steps. **Selected as primary live provider.**
  - *Recorded Mock Provider:* $0 cost, 100% offline, deterministic fixtures for 0, 1, 2, 3 routes, timeouts, 5xx errors, and rate limits. **Selected for test suite & offline operation.**
  - *Mapbox Directions API:* Commercial license, paid tiers ($0.50/1k), requires secret API keys, restrictive terms on permanent storage. *Rejected to prevent vendor lock-in.*
  - *Google Maps Directions API:* Commercial license, expensive ($5.00/1k), Section 3.2.4 prohibits caching/storage; Section 3.2.3 forbids automated street imagery scraping. *Rejected.*
- **Terms Reviewed:** Yes; OSRM and OSM data use ODbL; allows caching, storage, geometry analysis, and segment decomposition.
- **Imagery Guardrail Noted:** **YES (Rule 8).** Routing provider terms do **not** grant rights to extract or download street-level imagery. Imagery acquisition is strictly decoupled and deferred to Phase 14 via dedicated permitted sources.

---

## 2. Interfaces Implemented

Implemented abstract interface `RoutingProvider` in [`src/routing/interfaces.py`](file:///d:/New%20folder%20(3)/src/routing/interfaces.py) with concrete implementations in [`src/routing/mock_adapter.py`](file:///d:/New%20folder%20(3)/src/routing/mock_adapter.py) and [`src/routing/osrm_adapter.py`](file:///d:/New%20folder%20(3)/src/routing/osrm_adapter.py):
- `get_routes(request: RouteRequest) -> RouteResponse`
- `get_route_geometry(route_id: str) -> Optional[RouteGeometry]`
- `get_segment_metadata(route_id: str) -> List[RouteSegment]`

---

## 3. Edge-Case Behaviour (Observed)

- **Fewer than 4 routes (Rule 10):** Returns strictly the actual routes returned. Emits disclosure limitation `fewer_than_four_routes_returned`. Never synthesizes, duplicates, or pads routes to a fixed count.
- **No routes found:** Returns empty list `routes: []`, categorical status `NO_ROUTES_FOUND`, limitation `zero_routes_returned`.
- **Network timeout:** Bounded retry policy (3 retries with exponential backoff $0.5s \times 2^{k-1}$); on exhaustion surfaces explicit `PROVIDER_TIMEOUT` with error message.
- **Provider error (5xx):** Bounded retries (3 retries); on exhaustion surfaces `PROVIDER_ERROR` with HTTP status explanation.
- **Rate limited (429):** Surfaces `RATE_LIMITED` without unnecessary retry spamming.

---

## 4. Route Segmentation & Stable IDs

- **ID Scheme:** `seg-{route_id}-{sequence:04d}` (e.g. `seg-route_mock_alpha-0000`, `seg-route_mock_alpha-0001`).
- **Granularity:** Target length $\sim 200\text{ m}$ (bounded in $[50\text{ m}, 500\text{ m}]$) to match street imagery assessment requirements.
- **Geodesic Distance:** Haversine formula implemented in `haversine_distance_m` computing accurate metric segment lengths ($L_i$) for downstream deterministic risk scoring.
- **Stability:** Repeated queries with identical inputs yield identical, byte-identical segment IDs and sequence orders (verified by test).

---

## 5. Provenance

Every `RouteResponse` records:
- `provider`: Provider identifier (`osrm` or `mock_routing`).
- `request_id`: Unique request trace identifier (`mock-req-...` or `osrm-...`).
- `retrieved_at`: UTC ISO-8601 timestamp.
- `limitations`: Exhaustive list of active operational disclosures.

---

## 6. Secrets & Security

- **Stored in `.env` only:** Yes (Rule 13). Any future commercial keys are loaded strictly via environment.
- **Nothing committed:** Confirmed. Zero API tokens, passwords, or credentials exist in source code or tracked files.

---

## 7. Test Results (Empirical & Reproducible)

- **Test Command:** `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`
- **Passed / Total:** **59 / 59 passed (100%) in 5.95s**
- **Routing Unit Tests:** 13 dedicated test cases in [`tests/unit/test_routing_adapter.py`](file:///d:/New%20folder%20(3)/tests/unit/test_routing_adapter.py):
  - `test_rule_10_no_route_padding_two_routes`: PASS
  - `test_rule_10_single_route_not_padded`: PASS
  - `test_zero_routes_edge_case`: PASS
  - `test_provider_timeout_edge_case`: PASS
  - `test_provider_error_edge_case`: PASS
  - `test_rate_limited_edge_case`: PASS
  - `test_stable_segment_identifiers`: PASS
  - `test_haversine_distance_computation`: PASS
  - `test_segmenter_linestring_subdivision`: PASS
  - `test_interface_compliance_and_metadata_retrieval`: PASS
  - `test_rule_8_imagery_guardrail_in_config`: PASS
  - `test_factory_creation`: PASS
  - `test_serialization_contracts`: PASS

---

## 8. Validation Checklist

| # | Check | Status | Empirical Evidence |
|---|---|:---:|---|
| V1 | Provider decided | PASS | Selection of OSRM (live) and MockRoutingAdapter (test) documented in config and report. |
| V2 | Interface-only coupling | PASS | Consumers depend strictly on `RoutingProvider` ABC. |
| V3 | No fabrication | PASS | Rule 10 verified: 1 or 2 returned routes emit exactly 1 or 2 routes (never padded). |
| V4 | Edge cases handled | PASS | All 5 edge cases (fewer than 4, 0, timeout, error, rate limit) tested and passing. |
| V5 | Stable segment IDs | PASS | Deterministic `seg-{route_id}-{seq:04d}` verified across repeated executions. |
| V6 | Provenance recorded | PASS | `provider`, `request_id`, `retrieved_at`, and limitations captured in every response. |
| V7 | Secrets safe | PASS | Zero credentials committed. Local `.env` only. |
| V8 | Tests pass | PASS | 59/59 unit and integration tests passing. |

---

## 9. Limitations & Honesty Note

1. **Routing Only:** Routing responses provide polyline and GeoJSON geometries, steps, and road maneuver summaries. They do **not** provide road surface condition, hazard density, or imagery.
2. **Imagery Guardrail:** Using OSRM or any routing provider does **not** grant street-level imagery rights.
3. **Public Demo Endpoint:** The public demo endpoint `https://router.project-osrm.org` is intended for testing and development. High-throughput production usage should deploy a local containerized OSRM instance.

---

## 10. Result & Next Phase

- **Result:** **COMPLETE**
- **Next Phase:** **PHASE_14 — Permitted Imagery Acquisition Adapter**
- **Next Phase Authorised:** Pending immediate execution per user direction.
