# PHASE 23A — Real Road Imagery Feasibility Audit

> **Status:** COMPLETE (read-only audit) · **Date:** 2026-10-14 · **Workspace:** `D:\New folder (3)`
> **Type:** read-only audit — **no source files changed, no datasets or images downloaded,
> no checkpoints trained or modified, no tokens read or printed, no network calls to
> live imagery services performed.**
> **Governing:** `master_rules.md` (Rules 1, 8, 9, 10, 14, 19, 20), `docs/TRAINING_RULES.md`,
> `docs/PRD.md`, `docs/TRD.md` (§10), `docs/ARCHITECTURE.md` (§8),
> `docs/reports/COMPLETE_PROJECT_AUDIT.md`, `docs/reports/PHASE_22_report.md`.
> **Evidence convention:** **[VERIFIED]** = executed/observed this audit · **[CODE]** =
> confirmed by reading source · **[ASSUMPTION]** = not verified · **[UNKNOWN]** = needs a
> decision/asset.
> **The single file created by this phase is this report.**

---

## 1. Objective

Determine how SafeRoute AI can obtain **genuine road images that correspond to the actual
road segments of each route**, and honestly assess whether the current code does this, what
is missing, and whether it is safe to enable real imagery.

---

## 2. Existing implementation and relevant file paths

| Concern | File | Role |
|---|---|---|
| Imagery provider contract | `src/imagery/interfaces.py` | `ImageryProvider.get_imagery_for_segment(segment, permitted_source)` |
| Domain schemas | `src/imagery/schemas.py` | `ImageRef`, `ImageryResult`, `ImageryStatus`, `ImageryUnavailable` |
| Local/demo adapter | `src/imagery/adapter.py` | `PermittedImageryAdapter`; permitted-source registry; **fixed-coordinate local archive** |
| Live provider | `src/imagery/mapillary_provider.py` | `MapillaryImageryProvider`, `MapillaryHttp`; bbox `/images` query + thumbnail cache |
| Spatial matcher | `src/imagery/matcher.py` | `point_to_segment_distance_m`, `SegmentImageryMatcher` (25 m buffer) |
| Staleness | `src/imagery/staleness.py` | `StalenessEvaluator` (180-day policy) |
| Imagery config | `config/imagery.yaml` | Permitted sources, storage, matching (25 m), staleness (180 d), guardrails |
| Runtime provider selection | `src/config/settings.py`, `config/app.yaml` | `imagery_source`, `imagery_fallback_source`, Mapillary knobs |
| `.env` loader | `src/config/env.py` | stdlib loader; `MAPILLARY_ACCESS_TOKEN` read here |
| Secret template | `.env.example` | Documents `MAPILLARY_ACCESS_TOKEN` (placeholder only) |
| Live wiring | `src/api/bootstrap.py` | `build_imagery_provider`: Mapillary when token present, else local archive |
| Orchestration | `src/api/pipeline.py` | Per-segment imagery → detector → aggregator → risk engine |
| Route → segment | `src/routing/segmentation.py`, `src/routing/schemas.py` | Deterministic `seg-{route_id}-{seq:04d}`, 200 m target / 500 m max |
| Aggregation | `src/risk/aggregate.py` | Coverage status, confidence filter, **within-image** IoU dedup |
| Risk engine | `src/risk/engine.py` | `route_score=None` for unassessed/failed; PHASE_22 outcome fields |
| API | `src/api/app.py` | `/api/health` `capabilities.live_imagery`; serves frontend |
| Frontend | `frontend/app.js`, `frontend/index.html` | Shows coverage/outcome/attribution; **does not render acquired images** |
| Tests | `tests/unit/test_imagery_adapter.py`, `tests/unit/test_mapillary_provider.py`, `tests/unit/test_settings_env.py`, `tests/unit/test_api.py`, `tests/integration/test_end_to_end_api.py`, `tests/integration/test_end_to_end_pipeline.py` | Hermetic imagery/matcher/provider tests |

---

## 3. Verified current behavior

### 3.1 Provider selection
- **[CODE]** `build_imagery_provider(settings)` returns `MapillaryImageryProvider(...)` **only if**
  `settings.imagery_source == "mapillary"` **and** `settings.mapillary_token` is non-empty;
  otherwise it returns `PermittedImageryAdapter` (local archive).
- **[CODE]** `config/app.yaml` defaults `imagery_source: "mapillary"` and
  `imagery_fallback_source: "workspace_dashcam_v1"`.
- **[CODE]** `MAPILLARY_ACCESS_TOKEN` is read via `get_env(...)` in `settings.py`; the token is
  excluded from `Settings.to_safe_dict()` (redacted) and from `/api/config`.

### 3.2 Live imagery is NOT enabled / NOT verifiable now
- **[VERIFIED]** `.env` is **absent** (`Test-Path "D:\New folder (3)\.env"` → `False`).
- **[VERIFIED]** `MAPILLARY_ACCESS_TOKEN` is **not set** in the process shell environment.
- **[VERIFIED]** No token is stored anywhere in the workspace (only the placeholder key in
  `.env.example`).
- **Consequence:** the live Mapillary path has **never executed in this workspace**; the
  end-to-end system currently runs the **local demo archive** path. No live imagery claim is
  made or possible here (Rule 14, Rule 20).

### 3.3 Mapillary request shape **[CODE]**
`MapillaryImageryProvider.get_imagery_for_segment`:
1. Rejects a non-permitted source → `DISALLOWED_SOURCE`.
2. No token → returns the caller fallback with limitation
   `live_mapillary_disabled_no_token_using_local_archive`.
3. Builds `bbox` from the segment geometry + 25 m buffer via `_bbox_for_coords`.
4. Queries `GET https://graph.mapillary.com/images` with
   `fields=id,captured_at,compass_angle,geometry,thumb_1024_url`, `bbox`, `limit=max(4·3,10)=12`.
5. Filters items by `point_to_segment_distance_m <= 25 m`, sorts, keeps ≤ 3.
6. Downloads `thumb_1024_url` once into `data/imagery/mapillary/{id}.jpg` (git-ignored),
   applies staleness, emits `ImageRef` with source `mapillary`, licence `CC-BY-SA 4.0`.
7. Error handling: `401/403` → **fallback to local archive**; `429` → `INACCESSIBLE`
   (`mapillary_rate_limited`); other HTTP/exception → `INACCESSIBLE`.

### 3.4 Tests executed this audit (safe, hermetic)
Command:
```
.\.venv\Scripts\python.exe -m unittest tests.unit.test_imagery_adapter tests.unit.test_mapillary_provider tests.unit.test_settings_env
```
Result **[VERIFIED]**: `Ran 16 tests … OK` (8 + 6 + 2). These are offline (`FakeHttp`) /
local-archive tests and require no token or network. The PHASE_22 report records the full
suite at `128 tests … OK`.

---

## 4. Missing credentials / external requirements

| Requirement | Status |
|---|---|
| Mapillary client/user access token (`MAPILLARY_ACCESS_TOKEN`) | **[UNKNOWN]** — not present; must be created by the user at the Mapillary developer dashboard |
| `.env` file inside workspace (git-ignored) | **[UNKNOWN]** — absent |
| Network egress to `graph.mapillary.com` | **[ASSUMPTION]** — not exercised here |
| Mapillary imagery coverage at the target coordinates (Bengaluru) | **[UNKNOWN]** — coverage density not measured |
| Confirmation of Mapillary licence/attribution per image and current Terms of Use | **[UNKNOWN]** — code hardcodes `CC-BY-SA 4.0`; must be verified against Mapillary's live terms |
| YOLO11 checkpoint (for detection on acquired images) | exists (`models/training/saferoute-yolo11-v1/weights/best.pt`), but **accuracy is low** (see §7) |

### 4.1 Mapillary API requirements (verified from the official developer documentation, read 2026-10-14)
- **Authentication:** all `graph.mapillary.com` requests require a token (client or user
  access token); sent via `?access_token=XXX` or `Authorization: OAuth XXX`. Query-param
  use is **strongly discouraged for user tokens**; the current code uses the query param
  (acceptable for a client token).
- **`/images` bbox constraint (effective 2026-01-16):** the `bbox` area **must be smaller
  than 0.01 degrees square**; larger areas require the `mapillary-python-sdk`.
- **Fields available:** `id, captured_at, compass_angle, computed_geometry, geometry,
  is_pano, height, width, quality_score, creator, organization, sequence,
  thumb_256/512/1024/2048/original_url` … The code requests only a subset.
- **Rate limits:** search APIs (`/images?bbox=…`) **10,000/min/app**; entity APIs
  **60,000/min/app**; vector tiles **50,000/day**.
- **New radius search (2026-04):** `/images?...&lat=&lng=&radius=` supports `radius ≤ 50 m`
  and `limit ≤ 100` — a natural fit for the 25 m matcher, but not used by the current code.

### 4.2 Image-usage / attribution restrictions
- **[CODE]** The project asserts `mapillary` is `CC-BY-SA 4.0` (allowed for commercial use,
  ML inference and local storage) in `config/imagery.yaml`, and `frontend/index.html`
  displays `Imagery (if enabled) © Mapillary contributors (CC-BY-SA 4.0)`.
- **[UNKNOWN]** Per-image licence is **not** fetched/recorded; Mapillary imagery can belong
  to organizations with different terms. Attribution is displayed at the page footer only,
  not attached to a specific acquired image.
- **[CODE]** Google Street View is explicitly disabled in `config/imagery.yaml` with a reason
  citing §3.2.3 — consistent with Rule 8.

---

## 5. Route-to-image matching: limitations and defects

### 5.1 Fixed-coordinate fallback (confirmed defect — the audit's B3)
- **[CODE]** `PermittedImageryAdapter._load_local_archive_catalog` indexes
  `logs/evaluation/qualitative_samples/*.jpg` (real dashcam/dataset frames) and assigns
  **synthetic coordinates** anchored at Bengaluru `(77.5946, 12.9716)` with
  `+idx·0.001°` offsets — unrelated to any real route.
- **[VERIFIED]** Instantiated the adapter: `catalogue size: 20`; first entries
  `(77.5946, 12.9716)`, `(77.5956, 12.9726)`, `(77.5966, 12.9736)`; last
  `(77.6136, 12.9906)`; `storage_dir: D:\New folder (3)\data\imagery`. All 20 frames share
  handed `captured_at: 2025-02-19T14:30:00Z`.
- **Impact:** any route near central Bengaluru receives up to 3 real pothole/crack images
  that **do not correspond to those road segments**, and the segment is reported as
  `assessed`. Routes elsewhere get `UNMATCHED`. This is the demo path the running system
  currently uses (no token), and it is the same path used as the **auth-failure fallback**
  inside the Mapillary provider (401/403 → local archive).

### 5.2 Matcher is point-to-vertex, not point-to-segment
- **[CODE]** `point_to_segment_distance_m(pt, line_coords)` returns the **minimum Haversine
  distance to the vertices**, ignoring the perpendicular projection onto the segment edges.
- **Impact:** for a sparse long polyline, a camera point that lies **on** a long straight
  edge but is far (in vertex terms) from either endpoint is wrongly excluded. This can
  produce false `UNMATCHED` (under-coverage, honest but lossy) — and the symmetric case can
  accept a point near a vertex that is off the actual edge.

### 5.3 Duplicate-image / double-count risk (confirmed gap)
- **[CODE]** Matching is per-segment with a 25 m buffer and no cross-segment/cross-route
  image identity check. The same Mapillary image (or archive frame) within 25 m of two
  adjacent segments is returned for **both** and its hazards counted **twice**.
- **[VERIFIED]** `config/risk_engine.yaml` declares
  `hazard_metric.dedup_adjacent_segments: true` and `adjacent_boundary_iou: 0.50`, **but
  `grep` for those keys across `src/` returns no matches** — the setting is **not
  implemented**. This directly contradicts TRD §9 / ARCHITECTURE §7 de-duplication intent.

### 5.4 Metadata completeness
- **[CODE]** `ImageRef` records `image_id, file_path, source, licence, retrieved_at,
  captured_at, coordinates, distance_to_segment_m, is_stale, status`.
- **[CODE]** The Mapillary provider does **not** capture `is_pano`, `quality_score`,
  `creator`, `organization`, `sequence`, `width/height`, and does **not** use
  `compass_angle` for heading-aware matching. Licence/attribution is hardcoded per source,
  not per image.
- **Impact:** weaker provenance, no per-image attribution string for CC-BY-SA compliance,
  no panorama/quality filtering (panoramas may be poorly framed for hazard detection).

### 5.5 Staleness policy
- **[CODE]** 180-day staleness flag with disclosure; missing timestamp → stale
  ("freshness cannot be verified"). Applied in both providers. Reasonable and honest.

### 5.6 bbox size vs. the Mapillary constraint
- **[CODE]** `_bbox_for_coords` pads by 25 m and returns min/max lon/lat. For segments capped
  at 500 m this is ~0.005° , under the 0.01° square rule; but there is **no explicit guard**
  that clamps/rejects a bbox that exceeds 0.01° square. A long/curvy geometry (or an
  unexpected provider payload) could trigger an API error that surfaces as `INACCESSIBLE`.

---

## 6. Can the architecture assess all routes without pretending?

**[VERIFIED] Yes, at the scoring layer** (this is the strong part of the system):
- `pipeline._analyze_route` calls imagery per segment and passes only available images to
  the detector; `expected_image_count` drives coverage.
- `HazardAggregator.assess_segment` marks `UNASSESSED` when no imagery / no usable results,
  `FAILED` when all images fail, `PARTIALLY_ASSESSED` when coverage < 1.
- `DeterministicRiskEngine.score_route` returns `route_score = None` for fully
  unassessed/failed routes and never assigns 100 to unassessed segments; PHASE_22 added the
  `detection_outcome` taxonomy (`hazards_detected | no_hazards_detected |
  insufficient_coverage | detector_failed | unassessed`) and a "100 ≠ safe" note.
- `_build_comparison` ranks only routes with a real score and lists the rest as
  `unassessed_route_ids`; the frontend shows unassessed rows and the safety note.
- Negative-path tests exist (`AllMissingImageryProvider`, `HalfImageryProvider`,
  `FailingRoutingProvider`) and pass.

**Caveat [VERIFIED]:** the assessment is honest **about coverage**, but when the **local
demo archive** is in use the *content* is not route-corresponding (§5.1). So a Bengaluru
route can be reported `assessed` with a real score derived from unrelated imagery. Honesty
is preserved about *availability*, not yet about *photo-to-place correspondence*.

---

## 7. Required changes to enable real imagery safely

### 7.1 Configuration / environment (no secrets in the repo)
1. **Provide the token out-of-band:** create `D:\New folder (3)\.env` with
   `MAPILLARY_ACCESS_TOKEN=<user token>` (git-ignored). Never commit it; never paste it
   into reports/logs. `config/app.yaml` already sets `imagery_source: "mapillary"`.
2. **Explicit demo/real mode flag [PROPOSED]:** add e.g.
   `SAFEROUTE_IMAGERY_MODE=demo|real` (or config key) so the local archive is only used
   when the operator *deliberately* selects demo mode, with a loud disclosure. Do **not**
   silently fall back to the fixed-coordinate archive.
3. **Mapillary knobs [PROPOSED]:** expose `is_pano=false` filter, optional
   `quality_score` floor, and prefer the new `lat/lng/radius` search for ≤ 50 m.

### 7.2 Code changes [PROPOSED]
| # | File(s) | Change | Reason |
|---|---|---|---|
| C1 | `src/imagery/adapter.py` | Remove or gate the `+idx·0.001°` Bengaluru anchoring; if retained for demos, require an explicit demo flag and label images as `unmatched_to_route`/`demo`; never present them as route-corresponding. | Fix B3 / §5.1 |
| C2 | `src/imagery/mapillary_provider.py` | On `401/403`, do **not** substitute the geo-unrelated archive; return `INACCESSIBLE` with a clear limitation (or use only a truthfully geo-tagged fallback). | Avoid mismatched imagery masquerading as segment evidence |
| C3 | `src/imagery/matcher.py` | Implement true point-to-segment (perpendicular) distance and optionally heading (`compass_angle`) gating. | §5.2 |
| C4 | `src/risk/aggregate.py` (+ `engine.py`) | Implement cross-segment image de-duplication (by `image_id`, and/or the declared `dedup_adjacent_segments` / `adjacent_boundary_iou`) so one photo's hazard is not counted on multiple segments. | §5.3 |
| C5 | `src/imagery/mapillary_provider.py` / `schemas.py` | Request and persist `is_pano, quality_score, creator, sequence` and per-image attribution; optionally skip panoramas. | §5.4 provenance / CC-BY-SA compliance |
| C6 | `src/imagery/mapillary_provider.py` | Guard `bbox` to < 0.01° square (clamp, split, or use radius search). | §5.6 / API constraint |
| C7 | `src/api/app.py`, `frontend/app.js` | Optionally surface acquired image thumbnails + per-image attribution, and a clear `demo vs real` banner. | Let users see genuine imagery; honest mode signalling |
| C8 | `src/config/settings.py` | Ensure the token can never be logged (already redacted) and that a missing token disables the "live_imagery" capability (already true). | Rule 13 |

> **No code or config was changed in this phase.** Items above are proposals for a
> separately approved implementation phase.

---

## 8. Proposed tests (hermetic; no token, no live network)

Extend the existing offline suites (`test_mapillary_provider.py`, `test_imagery_adapter.py`,
`test_end_to_end_api.py`) using injected `FakeHttp`/fake providers:

1. **No fixed-coordinate imagery (B3):** assert the non-demo adapter returns `UNMATCHED`
   for coordinates outside a known archive and never fabricates coordinates; assert demo
   mode is explicitly flagged and disclosed.
2. **True point-to-segment matching:** a point on the middle of a long straight edge (far
   from vertices) matches; a point 30 m perpendicular does not.
3. **Cross-segment de-duplication:** one image id within range of two adjacent segments is
   counted **once** at route level; assert against the declared
   `dedup_adjacent_segments` policy.
4. **Mapillary bbox guard:** generated `bbox` is always < 0.01° square for supported
   segments; oversized geometry yields a controlled `INACCESSIBLE`/`UNMATCHED`, not a crash.
5. **Metadata/provenance:** provider records `is_pano`, `quality_score`, `creator`,
   `sequence`, and a per-image attribution string; panorama filtering works.
6. **Auth-failure honesty (C2):** simulate `401/403` and assert the result does **not**
   silently become geo-mismatched imagery (returns `INACCESSIBLE` or a truthfully disclosed
   path).
7. **Secret hygiene:** `Settings.to_safe_dict()`, `/api/config`, `/api/health` and logs never
   contain the token value (extend `test_settings_env.py`).
8. **Coverage honesty regression:** an imagery provider that returns images for some
   segments only yields `partially_assessed` with unassessed remainder never scored 100
   (already covered by `HalfImageryProvider`; keep as the guardrail).

These tests validate the integration **contract** without a token or unreliable live
service. A **live smoke test** (one real token + one known-covered coordinate) should be a
separate, explicitly-approved, manually-run check — not part of the default suite.

---

## 9. Risks

| Risk | Severity | Notes |
|---|---|---|
| Sparse/no Mapillary coverage at target roads | High | Not measurable without a token; would yield mostly `UNASSESSED` (honest but low utility). |
| Fixed-coordinate fallback mislabels unrelated images as segment evidence | High | §5.1; current demo + auth-fallback path. |
| Cross-segment double counting of the same photo | High | §5.3; declared-but-unimplemented policy. |
| Low detector accuracy (P≈0.14–0.19, R≈0.17–0.22 on a 40-image sample) | High | Even with real images, hazard detection is weak (COMPLETE_PROJECT_AUDIT §5 B4). |
| CC-BY-SA attribution/licence per image not enforced | Medium | Footer-only attribution; per-image provenance missing. |
| bbox > 0.01° API errors | Medium | §5.6. |
| Rate limiting / token exposure | Medium | 10k/min search limit; token redaction already correct, but `.env` hygiene is on the operator. |
| UI does not display images | Low/Medium | Users cannot visually verify the evidence yet. |
| Panorama/warped frames degrade detection | Low/Medium | No `is_pano` filter. |

---

## 10. GO / NO-GO recommendation

**NO-GO — do not enable live real imagery with the current code as-is.** Evidence:
- The live path has **never been exercised** here (`.env` absent, no token) — it cannot be
  claimed to work (Rule 14/20).
- The system's currently-active imagery path is the **fixed-coordinate Bengaluru demo
  archive**, which associates real pothole images with the **wrong** road segments (B3),
  including as the Mapillary auth-failure fallback.
- The declared cross-segment de-duplication policy is **not implemented**, so the same
  photo can inflate hazard counts across adjacent segments.
- The matcher is point-to-vertex, so genuine on-road images can be missed.

**GO — but only as a scoped, separately-approved implementation phase (PHASE 23B), in this
order:**
1. C1 + C2 (remove/gate the fixed-coordinate fallback; make auth failure honest) — these are
   safety- and honesty-critical.
2. C4 (cross-segment de-duplication) and C3 (true point-to-segment matcher).
3. C5 + C6 (metadata/attribution + bbox guard).
4. Add tests §8.1–§8.7; keep them hermetic.
5. Obtain a Mapillary token out-of-band and run **one** manual live smoke test on a
   known-covered coordinate, recording coverage honestly (no fabricated availability).
6. Separately, address detector accuracy (P1) — real imagery alone will not produce a
   trustworthy hazard signal.

---

## 11. Evidence appendix (executed this audit)

```
# 1. Environment / credentials
Test-Path "D:\New folder (3)\.env"                 -> False
$env:MAPILLARY_ACCESS_TOKEN                        -> not set
.gitignore                                         -> ignores .env and data/imagery/

# 2. Imagery cache contents (no real imagery present)
data/imagery/...                                   -> only _test_mapillary/12345.jpg (test artifact)

# 3. Local archive catalogue (fixed-coordinate demo)
catalogue size: 20
first: dashcam_20250219_165225 (77.5946, 12.9716) 2025-02-19T14:30:00Z
last:  dashcam_vlcsnap-2025-02-19-17h09m39s506 (77.6136, 12.9906)
storage_dir: D:\New folder (3)\data\imagery

# 4. Declared-but-unimplemented de-duplication
grep "dedup_adjacent_segments|adjacent_boundary_iou" src/   -> No matches found

# 5. Focused hermetic imagery tests
.\.venv\Scripts\python.exe -m unittest tests.unit.test_imagery_adapter \
    tests.unit.test_mapillary_provider tests.unit.test_settings_env
-> Ran 16 tests in 0.035s  OK

# 6. Working tree (pre-existing, NOT modified by this audit)
git status --porcelain -> 45 entries (PHASE_22-era uncommitted changes); no new edits made here.
git log -3 -> a3ebf8d (phases 15-18), 4bfa773 (13-14), a8c0bd5 (05-12)
```

**External documentation consulted (read-only):** Mapillary Graph API documentation
(`https://www.mapillary.com/developer/api-documentation`), read 2026-10-14 — authentication,
`/images` bbox < 0.01° square constraint, field list, rate limits, and the April-2026 image
radius search.

---

## 12. Honesty statement

This audit contains **no token, credential or secret**. It makes **no claim that live
Mapillary imagery works** — that path is unexercised. It distinguishes **[VERIFIED]** facts
from **[CODE]**, **[ASSUMPTION]** and **[UNKNOWN]** items; it did not download datasets or
images, retrain or alter any YOLO checkpoint, or modify any file other than creating this
report. The fixed-coordinate fallback, the point-to-vertex matcher, and the
unimplemented cross-segment de-duplication are reported as defects, not hidden.
