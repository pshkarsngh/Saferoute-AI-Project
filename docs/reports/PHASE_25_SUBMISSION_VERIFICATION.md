# SafeRoute AI — PHASE 25: Submission Verification

> **Phase:** PHASE 25 — end-to-end submission verification of the phase-25 route
> comparison policy work and the three small close-out fixes.
> **Date executed:** 2026-10-18 (UTC) · **Workspace:** `D:\New folder (3)` · **Branch:** `main`
> **Mode:** verification + three small, directly-justified fixes. No retraining, no
> checkpoint replacement, no risk-formula/threshold/config change, no provider
> configuration changed, no commit/push. The main phase used **no** live provider and made
> **no** external request; a separate, explicitly-authorized, read-only **live diagnostic**
> (Nominatim + OSRM + Mapillary) was subsequently executed and is recorded in §10.
> **Governing rules:** `master_rules.md` 1, 2, 7, 8, 9, 10, 12, 13, 14, 15, 17, 18, 19, 20.

---

## 0. Verification status in one line

**The application is verified end-to-end on mocked/offline providers and on the real
local configuration for startup and health. The live assessable-route workflow
(two or more sufficiently assessed routes produced by the real OSRM + Mapillary
pipeline) is NOT verified and remains BLOCKED** — see §5. The live provider components
themselves **have now been exercised live and PASS** (geocoding, routing, imagery
retrieval, downloads, detection) — see §10; the reason the workflow still cannot be
claimed is that **every live image retrieved was stale** under the 180-day policy, so no
route can currently be assessed as safe (§3.4, Rule 9).

---

## 1. Phase 1 — route-comparison policy fixes

**Defect (two failing tests in `tests/unit/test_route_comparison.py`).**

1. `build()` applied the `never_recommend_demo_evidence` guard to `eligible`, but
   `_rank_entry()` recomputed `sufficiently_assessed` from coverage alone. A demo
   route was therefore reported as `sufficiently_assessed: true` while simultaneously
   `eligible_for_recommendation: false` — an internally inconsistent record.
2. The "only one route could be defensibly compared" disclosure was gated on
   `len(ranked) > 1`, i.e. on *scored* routes only. When one route was unassessed
   (`status: unassessed`, not scored) and one was assessed, the comparison recommended
   a route with **no disclosure** that the other returned route could not be compared.

**Fix (single file, `src/risk/comparison.py`).**

- Added one shared policy predicate `_is_sufficiently_assessed(fraction, is_demo)`
  and used it in both `build()` and `_rank_entry()`, so `eligible` and
  `sufficiently_assessed` can no longer disagree.
- Threaded `unassessed_count` through `_decide()` → `_recommendation_reasons()`.
  Disclosure now fires on the number of *returned* routes, not scored routes:
  `"Only 1 of N returned route(s) was sufficiently assessed; the other M route(s)
  could not be defensibly compared."`
- The demo not-eligible reason now cites the real cause
  (`evidence class 'demo' is excluded by policy`) instead of the previous text,
  which falsely attributed it to a coverage shortfall.

**Explicitly unchanged:** `min_assessed_length_fraction`, `tie_tolerance_score`,
`never_recommend_demo_evidence`, every hazard/severity/weight constant, and the risk
engine (`src/risk/*` scoring) — Rules 7 and 18.

**Result:** `Ran 14 tests ... OK` for `tests.unit.test_route_comparison`.

---

## 2. Phase 2 — end-to-end verification (actual results)

All runs used the workspace venv `.\.venv\Scripts\python.exe`. Mock/offline providers
were selected by **runtime environment variables only** for the functional scenarios;
`config/app.yaml` was not modified. `data/imagery/mapillary/` contains only `.jpg`
frames with no geotag manifest, so no synthetic coordinates were invented (PHASE_23B).

### 2.1 Startup and health (real configuration, no outbound calls)

| Check | Result |
|---|---|
| `scripts/run_app.py --no-browser --port 8077` | starts cleanly |
| `GET /api/health` | `200`, `status: ok`, `model_version: saferoute-yolo11-v2` |
| Providers reported | `osrm`, `mapillary`, `overpass`, `nominatim`, `ollama` |
| Capabilities | `geocoding: true`, `live_imagery: true`, `live_llm: true` |

### 2.2 Frontend served and honest

| Check | Result |
|---|---|
| `GET /`, `/app.js`, `/styles.css` | all `200` |
| Served bytes vs disk | SHA-256 identical for `/app.js` |
| UI wiring | `frontend/app.js` calls the real `/api/*` endpoints (no hard-coded scores) |

### 2.3 Functional scenarios

| # | Scenario | Result |
|---|---|---|
| 1 | **All imagery missing** (mock, demo off) | both routes `status: unassessed`, `route_score: null`; `recommendation: null`; `comparability: all_routes_unassessed`. An absence is never reported as safe (Rule 9). |
| 2 | **One assessed + one unassessed** (`RouteComparer`) | recommended `route_a`, `reason: single_sufficiently_assessed_route`, and the Phase-1 disclosure sentence is present. |
| 3 | **Demo evidence only** (demo enabled) | scores `83.85` / `73.04` present, but both `sufficiently_assessed: false`, `eligible_for_recommendation: false`, `recommendation: null`, `comparability: demo_evidence_only`. Demo never becomes a real recommendation (Rule 20). |
| 4 | **Stale imagery** | demo frames return `is_stale: true`, `captured_at: null`, `coordinates: null`. Stale-only evidence now yields `recommendation: null`, `comparability: no_sufficiently_assessed_route`, and a `cannot_determine_reason` naming staleness (§3.4). |
| 5 | **Unmatched imagery** | `status: UNMATCHED`, limitation `missing_imagery_not_safe`. |

### 2.4 Model inference (permitted local imagery only — counts, not metrics)

| Check | Result |
|---|---|
| Single image | `pothole 0.4746`, bbox `[210.0, 415.0, 373.1, 462.5]` on `1027788324293941.jpg` |
| 20-image smoke over `data/imagery/mapillary/` | 2 images with detections, 2 detections total, both `pothole`, confidence `0.3373`–`0.4746` |

These are **execution counts only**, not accuracy metrics (Rule 14). Model metrics are
**not** re-measured here; see §6.

### 2.5 Error handling and security

| Check | Result |
|---|---|
| Geocoding disabled | `503 geocoding_disabled` |
| Malformed payload | `400 invalid_request` (×2) |
| Unknown analysis id | `404` (×3) |
| Path traversal `GET /../.env` | `404` — blocked, `.env` not served |
| `POST /api/facilities` | `200`, 6 items (context only, Rule 11) |

### 2.6 Persistence

`searches` 20 rows, `analyses` 20 rows, `scores` 37 rows; the sub-endpoints
`/hazards`, `/comparison`, `/explanation` all resolve for stored analyses.

---

## 3. Three close-out fixes (applied, with justification)

### 3.1 `scripts/run_app.py` — `SyntaxWarning` at import (fixed)

`scripts\run_app.py:8` documented a Windows path containing `\.v`, which Python
parsed as an invalid escape sequence and warned on every launch.

**Change:** module docstring `"""` → `r"""` (one character).
**Justification:** zero behaviour change; removes a spurious startup warning.
**Verified:** `python -W error::SyntaxWarning -c "import py_compile;
py_compile.compile(r'scripts\run_app.py', doraise=True); print('COMPILE_OK_NO_SYNTAXWARNING')"`
→ `COMPILE_OK_NO_SYNTAXWARNING`, and a clean start on port 8081.

### 3.2 `src/api/store.py` — dead `hazard_detections` table (fixed)

The schema (TRD §12) and the module docstring both declare hazard-detection
persistence for auditability (Rule 17), but `save_analysis()` never wrote a row, so
the table was always empty and the documented audit trail did not exist.

**Change:** `save_analysis()` now writes one row per supported hazard
(`route_id`, `segment_id`, `image_id`, `hazard_class`, `confidence`, `severity`,
`bbox_json`, `status`). Re-saving an analysis first clears that analysis's rows
(`DELETE ... WHERE analysis_id=?`) so persistence stays idempotent, mirroring the
existing `INSERT OR REPLACE` style.

**Justification chosen over dropping the table:** populating the declared table
restores the documented audit trail without touching the schema; dropping it would
have *removed* a documented TRD §12 entity and required a docstring/schema edit.
**Behavioural impact:** none on any API response — `/hazards` reads from the in-memory
record, unchanged.

### 3.3 `src/imagery/adapter.py` — demo path ignored the image cap (fixed)

`_demo_result()` returned the whole local archive for every segment, ignoring
`max_images_per_segment` (3). This only manifests when demo mode is explicitly
enabled (it is `false` by default in `config/app.yaml`).

**Change:** iterate `demo_candidates[: self.matcher.max_images]`.
**Justification:** the configured cap must apply uniformly; enabling a labelled demo
could otherwise multiply inference work by the entire archive.
**Behavioural impact:** none in the default configuration (demo off).

### 3.4 Stale imagery could justify a recommendation (fixed — safety)

**Finding (verified before the fix):** `ImageryResult.is_available` returns `True`
for `status: STALE`, so frames beyond the 180-day policy age were still run through
detection and still produced a score. Because the score was a normal score, a route
whose only evidence was stale could be **recommended** as the safest route, with the
staleness disclosed only as imagery metadata. That is a safety defect: stale evidence
cannot establish that a road is safe *now* (Rule 9 — missing/stale evidence is never
"safe").

**Fix (no formula, threshold, weight, or config change):**
- `src/api/pipeline.py:_analyze_route()` — classify a route's `evidence_class` as
  `stale` when any image used is stale (`is_stale` or `status: stale`); the risk
  score itself is unchanged. A limitation is appended naming the staleness.
- `src/risk/comparison.py` — a route whose `evidence_class` is `stale` fails the
  policy predicate `_is_sufficiently_assessed()`, exactly as demo evidence does, so
  it is **not** an eligible candidate for `recommended_route_id`. Ranking entries
  surface `evidence_class: stale`, and `cannot_determine_reason` names staleness when
  every scored route was stale-only.

**Scope note (conservative, deliberate):** exclusion is all-or-nothing at the route
level, mirroring the existing demo-evidence rule. A route that mixes fresh and stale
images is classified `stale` and therefore ineligible. This is intentionally stricter
than a per-segment freshness weighting, and changing it would require a documented
policy decision plus new formulas/thresholds, which are out of scope here.

**Regression tests** — `tests/unit/test_stale_fresh_regression.py` (4 tests, all
synthetic, labelled): fresh imagery all-clean (tie → no recommendation); **stale-only
evidence → `recommendation: null`, `comparability: no_sufficiently_assessed_route`**,
every ranking entry `eligible_for_recommendation: false` and `evidence_class: stale`;
missing imagery → `all_routes_unassessed` (absence is never safe); mixed fresh-vs-stale
where the *fresh* route carries the hazard — the stale route is ineligible, so the
hazard-bearing fresh route is recommended over the stale-clean route.

---

## 4. Test suite and startup re-verification (after the fixes)

| Check | Result |
|---|---|
| Full suite `python -m unittest discover -s tests` | **`Ran 191 tests in ~29 s — OK`** |
| Process exit code | **`EXITCODE=0`** (captured via `cmd /c … & echo EXITCODE=%ERRORLEVEL%`) |
| Test delta | 168 → **191** (+23 tests, all additive) |
| New tests | +4 persistence/image-cap (§3.1–3.3); +15 route-recommendation correctness (`test_route_recommendation_correctness.py`); +4 stale-imagery regression (`test_stale_fresh_regression.py`, §3.4) |
| Startup after fixes (port 8081, real config) | starts cleanly, **no** `SyntaxWarning` |
| `GET /api/health` | `200`, `saferoute-yolo11-v2`, providers `osrm`/`mapillary`/`overpass`/`nominatim`/`ollama` |

The negative-path test `test_hazard_detections_empty_when_none_detected` deliberately
asserts that **no detections produce no rows** — an absence is never recorded as a
hazard (Rule 9).

---

## 5. NOT verified — live assessable-route workflow (BLOCKED)

**The following workflow has not been exercised and must not be claimed as verified:**

> Two or more *sufficiently assessed* real routes produced end-to-end by the live
> OSRM routing + Mapillary imagery + detection + risk-scoring pipeline, compared and
> recommended with real geographically-matched evidence.

**Status: BLOCKED in the main phase.** `data/imagery/mapillary/` holds `.jpg` frames with
**no geotag manifest**, so frames cannot be geographically matched to route segments.
PHASE_23B forbids synthesising coordinates, and no permitted geotagged dataset is
available offline (Rules 8, 15, 19). Scenarios in §2.3 exercise this logic only against
mock/offline providers.

**Update (post-phase):** the blocker was subsequently attacked directly via a limited,
**read-only, live** run using the existing `.env` token and the live OSRM/Mapillary
endpoints. Retrieval, download, decoding, spatial matching and detection all **worked
live**; the workflow remains unclaimable only because **all live imagery retrieved was
stale** (>180 days). Full evidence and method in **§10**.

**Clearing the blocker fully requires one of (Rule 19 authorization):**
1. a live Mapillary dataset **fresher than the 180-day policy** (the coordinates, not the
   code, are the limitation), or
2. a **permitted, geotagged** local dataset added to the imagery registry.

**Live-verified by the post-phase diagnostic (§10):** OSRM routing and Nominatim
geocoding. **Still offline-verified only:** Overpass facilities and Ollama explanation.

---

## 6. Model metrics and dataset provenance (cited, not re-measured)

Model metrics were **not** re-measured in PHASE 25. Figures below are carried forward
from the existing phase reports and are labelled with their source and their limits:

| Figure | Source | Stated limit |
|---|---|---|
| mAP@0.5 ≈ 0.26, `pothole` + `crack` | `README.md` limitations / PHASE 24 baseline | a **single** dashcam dataset; not a global safety guarantee |
| v2 F1 `0.297` → `0.327` @ conf 0.25 | `docs/reports/PHASE_24F_CONFIDENCE_SWEEP.md` | 601-image **unseen micro** holdout |

**Dataset provenance (Rule 15):** primary source is the Roboflow Universe
*Pothole, Crack & Manhole* dataset (Zenodo record `18528034`, **CC BY 4.0**), with
RDD2022 (6 countries) as the wider reference corpus. The DATA-YOLO experimental
checkpoint's provenance is **explicitly unresolved** and is documented as such in
`docs/reports/DATA_YOLO_TRAINING_PREP.md`; it is not promoted for serving — the
serving checkpoint remains `models/training/saferoute-yolo11-v2/weights/best.pt`
(`config/detection.yaml`).

---

## 7. Setup instructions and exclusions

**README quick start verified against the workspace:** `.venv` present,
`requirements.txt` installed, `.env.example` present, `scripts\run_app.py` launches
API + UI on `127.0.0.1:8000`. The README's "Known limitations (honest)" section
matches the actual configuration (2-class detector, deterministic engine owns scoring
per Rule 7, LLM only explains per Rule 12, Google Street View intentionally not wired).

**Git exclusions verified — none of these are tracked or staged:**

| Path | Status |
|---|---|
| `.env` | ignored by `.gitignore:2`; **untracked** (`git ls-files --error-unmatch .env` → pathspec error) |
| `data/datayolo_prep/` | ignored by `.gitignore:18` |
| `models/` (incl. `best.pt` weights) | ignored by `.gitignore:35` |
| `.env.example` | tracked, contains placeholders only |

**Screenshots:** no new screenshots were captured in PHASE 25. Genuine pre-existing
visualisation artefacts live in `reports/phase24e/visualizations/` and
`models/evaluation/` from PHASE 24E/24D; the PHASE 25 evidence is the captured JSON
records of the §2.3 scenarios rather than images. Nothing was staged or re-generated
to create the impression of fresh evidence (Rule 14).

---

## 8. Complete change set

`git status --short` at the end of PHASE 25 (all **unstaged**, nothing staged, nothing
committed):

| File | Change |
|---|---|
| `src/risk/comparison.py` | Phase 1: shared policy predicate, disclosure threading, honest demo reason; **stale evidence ineligible for recommendation (§3.4)** |
| `src/api/pipeline.py` | classify `evidence_class: stale` when any image used is stale + disclose limitation (§3.4) |
| `scripts/run_app.py` | `r"""` docstring (removes `SyntaxWarning`) |
| `src/api/store.py` | populate `hazard_detections` idempotently |
| `src/imagery/adapter.py` | apply `max_images_per_segment` to the demo path |
| `tests/unit/test_api.py` | +3 hazard-detection persistence tests (additive) |
| `tests/unit/test_phase23b_imagery_integrity.py` | +1 demo image-cap test (additive) |
| `tests/unit/test_route_recommendation_correctness.py` | +15 synthetic route-recommendation correctness tests (untracked, additive) |
| `tests/unit/test_stale_fresh_regression.py` | +4 stale/fresh/missing/mixed imagery eligibility tests (untracked, additive) |
| `docs/reports/PHASE_25_SUBMISSION_VERIFICATION.md` | this report (untracked) |

Untracked additions (`??`) are new files, not modifications to existing tracked files.
Diffstat for **tracked** files: `7 files changed`. The only deletion in the test files
is the widened `DetectionRecord` import line.

**Not changed, deliberately:** `config/app.yaml`, `config/detection.yaml`,
`config/imagery.yaml`, `config/route_comparison.yaml`, any risk threshold/weight,
`src/risk/engine.py`, `src/risk/severity.py`, `src/risk/aggregate.py`, any model
checkpoint (still `saferoute-yolo11-v2`), the `data/datayolo_prep/` tree. `.env` is
untracked and gitignored — never staged.

---

## 9. Remaining blockers

1. **Live assessable-route workflow** (§5) — the live *components* now PASS (§10), but the
   workflow is still not claimable because **all live imagery retrieved was stale**; with
   the §3.4 policy a route cannot be declared safe on stale evidence. Full clearance needs
   Rule 19 authorization for a dataset/route with imagery **within** the 180-day policy.
2. **Provider paths** — Nominatim and OSRM are now live-verified (§10); Overpass
   facilities and Ollama explanation remain offline-verified only.
3. **DATA-YOLO provenance** — unresolved; experimental checkpoint not promoted.

No commit or push was performed. The change set is prepared and awaiting review.

---

## 10. Live integration diagnostic (executed, read-only) — PASS with one finding

**Authorization and mode.** Executed only after explicit user authorization, as a
**read-only diagnostic** using the live providers already configured in `config/app.yaml`
and the existing `MAPILLARY_ACCESS_TOKEN` in `.env`. All probe scripts lived outside the
repository (`%TEMP%\opencode\…`). **No project source, config, threshold, formula,
checkpoint, or dataset was modified.** The only writes were normal provider cache JPEGs
under the git-ignored `data/imagery/mapillary/` (`.gitignore:9`). The access token was
never printed or written; probe output handlers scrub any token-like text.

**Honesty boundary.** Coordinates came **only** from live Nominatim geocoding — none were
invented or synthesised (PHASE_23B rule respected). Live vs cached vs demo is labelled on
every row. These are **execution counts**, not accuracy metrics (Rule 14).

### 10.1 Live geocoding (source of all coordinates)

| Query | Provider | Status | Resolved coords |
|---|---|---|---|
| Vidhana Soudha, Bengaluru | nominatim | OK | 12.977209, 77.590002 |
| MG Road, Bengaluru | nominatim | OK | 12.975526, 77.606790 |
| Cubbon Park, Bengaluru | nominatim | OK | 12.974253, 77.592191 |

### 10.2 Live imagery retrieval + download (Mapillary)

`GET https://graph.mapillary.com/images` with `bbox`, `limit`, `fields=…thumb_1024_url`.

| Location | HTTP status | API items | Images returned | Result |
|---|---|---|---|---|
| Vidhana Soudha | 200 | 1 | 1 | live |
| MG Road | 200 | 1–2 | 1–2 (varies across calls) | live |
| Cubbon Park | 200 | 0 | 0 | `unmatched` (never treated as safe) |

Distinct live frames downloaded this diagnostic: **3**, all HTTP 200, `Content-Type:
image/jpeg`, PIL-decoded OK. `is_demo=False`, `source=mapillary`, `licence=CC-BY-SA 4.0`,
**no fallback engaged**, real coordinates populated, `distance_to_segment_m` ≤ 25 m (6.6 m
and 4.7 m on two frames). A second call for the same segment downloaded **0** further
files — served from the on-disk cache, as designed.

**Every retrieved frame is STALE** against the 180-day policy:

| image_id | bytes | dims | captured_at | age | status |
|---|---|---|---|---|---|
| 505126624000388 | 148693 | 1024×1024 | 2016-01-17 | 3926 d | stale |
| 732478869088213 | 58199 | 1024×512 | 2024-03-25 | 937 d | stale |
| 1454437511584512 | 64616 | 1024×512 | 2024-03-25 | — | stale |

Staleness is disclosed as a limitation, exactly as §3.4 requires; stale evidence never
becomes a safety claim (Rule 9).

### 10.3 Live OSRM routing + real segment imagery

Full route: **MG Road, Bengaluru → Vidhana Soudha, Bengaluru** (both endpoints from live
Nominatim).

| Check | Result |
|---|---|
| OSRM `provider` / `status` | `osrm` / `ok` |
| Routes returned | 1 (`2` for a longer route pair) |
| Distance / duration / segments | `2694 m` / `187 s` / `14` |
| Summary | `Route 1 via Doctor B R Ambedkar Veedhi` |

A **longer pair** (Vidhana Soudha → Kempegowda Intl. Airport) returned 2 live routes
(`33942 m`, 139 segments; `35888 m`, 158 segments), both `ok`. An intermittent
`provider_timeout` occurred on one early call (public demo server, 5 s configured timeout
× 3 retries) and did **not** recur on repeat.

Live imagery was then fetched **per real segment** (first 12 of 14):

| Outcome | Count |
|---|---|
| Segments probed | 12 |
| Segments with imagery | 10 |
| Segments `unmatched` (no imagery) | 2 |
| Images retrieved total | 28 |
| Newly downloaded (not cached) | 27 |
| **fresh / stale / demo** | **0 / 28 / 0** |

### 10.4 YOLO11 over live imagery

`HazardDetector` = `saferoute-yolo11-v2`
(`models/training/saferoute-yolo11-v2/weights/best.pt`), `conf=0.25`. All **28** live
frames processed; **6 detections total** across 4 images (2 `pothole`, 4 `crack`), rest
`no_detections`. Example: `pothole conf=0.807` and `0.408` on one frame. These are
counts only — **accuracy metrics for this run are NOT claimed** (Rule 14).

### 10.5 Finding — Mapillary `/images` returns a non-deterministic subset

For a **byte-identical** `bbox` request the endpoint returns **different item counts**:

| `limit` sent | Observed item counts | Distinct result sets |
|---|---|---|
| 10 (≈ provider default) | 1–9 | 6 / 6 runs |
| 25 | 6–22 | 5 / 6 |
| 50 | 8–37 | 6 / 6 |
| 100 | 39–43 | 3 / 6 |
| **200** | **43, 43, 43, 43, 43, 43** | **1 / 6 (stable)** |
| 500, 2000 | 43 (stable) | 1 / 6 |

**Root cause:** `src/imagery/mapillary_provider.py` sends `bbox` + `limit =
max(max_images*4, 10)` (i.e. **12** by default) with **no ordering/pagination**, so the
endpoint returns a small, arbitrary, non-reproducible window of the corridor. The probe
confirmed the endpoint is **stable once `limit ≥ 200`** for this bbox. `order_by` is
accepted but did not stabilise results; no `paging` cursor was returned.

**Impact:** identical inputs can select different images (MG Road returned 1 then 2);
we did **not** observe a case where this changed a safety verdict, and this is **not** a
defect we introduced. **No fix was applied** — increasing the limit changes provider
behaviour and would need review/authorization. A candidate one-line mitigation
(raise the request `limit`; optionally add `order_by=captured_at`) is recorded here as a
**proposal only**.

### 10.6 Diagnostic verdict

- **PASS (live):** Nominatim, OSRM routing, Mapillary retrieval/download/decoding,
  spatial matching, YOLO11 inference.
- **Workflow still not claimable:** every live frame is **stale**, so per §3.4 a route
  cannot be declared safe on this evidence.
- **Finding recorded, unfixed:** Mapillary result-set non-determinism at small `limit`
  (§10.5).
- **No project file changed by the diagnostic**; git working tree matched the pre-existing
  §8 change set before and after. Full test suite re-run: **`Ran 191 tests … OK`**.
