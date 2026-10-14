# PHASE 23B — Fix Critical Road Imagery Integrity Bugs

> **Status:** COMPLETE · **Date:** 2026-10-14 · **Workspace:** `D:\New folder (3)`
> **Type:** implementation phase (code + config + tests + this report).
> **No training, downloads, dataset changes, image downloads, token creation or network
> calls to live imagery services were performed. No existing checkpoint or dataset was
> modified.**
> **Governing:** `master_rules.md` (Rules 1, 7, 8, 9, 10, 13, 14, 17, 18, 19, 20),
> `docs/TRAINING_RULES.md`, `docs/PRD.md`, `docs/TRD.md` (§9.4, §10), `docs/ARCHITECTURE.md`
> (§7, §8), `docs/reports/PHASE_23A_IMAGERY_AUDIT.md`.
> **Evidence convention:** **[VERIFIED]** = executed/observed this phase · **[CODE]** =
> confirmed by reading source.

---

## 1. Objective

Implement the five imagery-integrity fixes requested by PHASE 23B:

1. Remove the misleading fixed-coordinate fallback (no synthetic geography).
2. Make Mapillary 401/403 auth failure honest (no unrelated sample substitution).
3. Implement the declared cross-segment image de-duplication policy.
4. Replace point-to-vertex matching with true point-to-segment distance.
5. Add focused, hermetic regression tests.

---

## 2. Files changed

| # | File | Change | Reason |
|---|---|---|---|
| 1 | `src/imagery/adapter.py` | Removed Bengaluru `+idx·0.001°` anchoring; local sample frames are now indexed with `coordinates=None` + `is_demo=True`; added explicit `demo_mode` (default OFF); added `_demo_result`. | Fix #1 (audit §5.1 / B3). |
| 2 | `src/imagery/schemas.py` | Added `ImageRef.is_demo` field + serialization. | Make demo imagery self-identifying (Rule 20). |
| 3 | `src/imagery/mapillary_provider.py` | 401/403 now returns `INACCESSIBLE` (no fallback); added `_redact` so the token can never appear in surfaced messages. | Fix #2 (audit §5.1 / C2). |
| 4 | `src/risk/aggregate.py` | Added pure function `deduplicate_adjacent_segment_hazards(...)` implementing the declared policy. | Fix #3 (audit §5.3 / C4). |
| 5 | `src/risk/engine.py` | Reads `hazard_metric.dedup_adjacent_segments` / `adjacent_boundary_iou`; applies de-dup in `score_route` before scoring. | Fix #3; makes the declared config real. |
| 6 | `src/api/pipeline.py` | Applies the same de-dup before scoring; hazard output now derives from the de-duplicated assessments. | Fix #3; keeps API hazard list consistent with the score. |
| 7 | `src/imagery/matcher.py` | True perpendicular point-to-segment distance (local equirectangular projection, clamped projection). | Fix #4 (audit §5.2 / C3). |
| 8 | `src/api/bootstrap.py` | Wires `imagery_demo_mode` into the local adapter; documents honest fallback. | Fix #1. |
| 9 | `src/config/settings.py` | Added `imagery_demo_mode` (default `False`) + `SAFEROUTE_IMAGERY_DEMO_MODE` env override. | Fix #1. |
| 10 | `config/app.yaml` | `imagery.demo_mode: false`. | Fix #1 (explicit, off by default). |
| 11 | `config/imagery.yaml` | Added `demo.enabled: false` + policy comment. | Fix #1. |
| 12 | `.env.example` | Documented `SAFEROUTE_IMAGERY_DEMO_MODE`. | Fix #1 (safe setup). |
| 13 | `src/risk/__init__.py` | Exported the de-dup helper. | Fix #3. |
| 14 | `tests/unit/test_phase23b_imagery_integrity.py` | New hermetic regression suite (20 tests). | Fix #5. |
| 15 | `docs/reports/PHASE_23B_report.md` | This report. | Rule 17. |

No other source file was edited. Pre-existing uncommitted changes in the working tree were
preserved and not claimed as this phase's work.

---

## 3. Behaviour before → after

### 3.1 Fixed-coordinate fallback (Fix #1)

- **Before:** `PermittedImageryAdapter._load_local_archive_catalog` indexed the 20
  `logs/evaluation/qualitative_samples/*.jpg` frames at synthetic coordinates
  `(77.5946 + idx·0.001, 12.9716 + idx·0.001)`. Any central-Bengaluru route was reported
  `assessed` using real pothole frames from **unrelated** roads; routes elsewhere returned
  `UNMATCHED`.
- **After:** No coordinate is ever synthesised. Local frames are indexed with
  `coordinates=None` and `is_demo=True` and can never match the spatial matcher. In normal
  mode a segment with no verified imagery returns an honest **`UNMATCHED`**
  (`missing_imagery_not_safe`). Demo imagery is returned **only** when `demo_mode` is
  explicitly enabled, is marked `is_demo=True`, carries no coordinates, and is disclosed with
  `demo_imagery_not_geographically_matched` and `demo_imagery_not_route_evidence`.

### 3.2 Mapillary auth failure (Fix #2)

- **Before:** HTTP 401/403 silently returned the local (geo-unrelated) archive via
  `_fallback_result(..., "mapillary_auth_failed_http_401_using_local_archive")`.
- **After:** 401/403 returns an explicit `INACCESSIBLE` result with limitations
  `mapillary_auth_failed`, `mapillary_auth_failed_no_substitution`, `missing_imagery_not_safe`.
  The fallback is **not** consulted. All surfaced error strings pass through `_redact`, so the
  access token can never appear in a message. The no-token path still uses the caller
  fallback (which is now itself honest).

### 3.2.1 De-duplication (Fix #3)

- **Before:** `config/risk_engine.yaml` declared `dedup_adjacent_segments: true` and
  `adjacent_boundary_iou: 0.50`, but no code referenced them; the same image within 25 m of
  two adjacent segments had its hazard counted twice.
- **After:** `deduplicate_adjacent_segment_hazards` removes later occurrences of the same
  physical hazard (same non-empty `image_id` + same hazard class, with an equivalent or
  IoU ≥ `adjacent_boundary_iou` bounding box) across segments, in route order. Removed
  severity is subtracted from the owning segment's `aggregate_hazard`. Hazards without an
  `image_id` and genuinely distinct hazards (different class / non-overlapping box) are
  preserved. The engine applies it in `score_route`; the pipeline applies the same function
  so the API hazard list matches the score. Configuration was **not** changed to hide the
  policy — it is now genuinely implemented.

### 3.2 Point-to-segment matching (Fix #4)

- **Before:** `point_to_segment_distance_m` returned the minimum Haversine distance to the
  polyline **vertices**, ignoring the perpendicular projection onto edges.
- **After:** It returns the true minimum distance to the nearest polyline **edge** using a
  local equirectangular projection with the projected point clamped to the edge extent. A
  camera in the middle of a long straight edge now matches; a point beyond the radius does
  not. Coordinate order `(lon, lat)` and all route schemas are unchanged.

---

## 4. Tests and results (executed this phase) [VERIFIED]

### 4.1 Baseline (before edits)
```
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
-> Ran 128 tests in 17.669s  OK
```

### 3.2 Focused imagery/risk suite (after changes)

```
.\.venv\Scripts\python.exe -m unittest tests.unit.test_imagery_adapter \
    tests.unit.test_mapillary_provider tests.unit.test_settings_env \
    tests.unit.test_phase23b_imagery_integrity tests.unit.test_hazard_aggregation \
    tests.unit.test_risk_engine tests.unit.test_detection_outcome
-> Ran 66 tests in 0.216s  OK
```

New suite alone:

```
.\.venv\Scripts\python.exe -m unittest tests.unit.test_phase23b_imagery_integrity
-> Ran 20 tests  OK
```

### 3.3 Full suite (after)

```
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
-> Ran 148 tests in 24.709s
OK
```

`148 = 128 (baseline) + 20 (new PHASE_23B tests)`. **[VERIFIED]** All pass; zero failures /
errors.

> **Known non-failing warning (pre-existing, not introduced here):** the `matcher.py` class
> docstring contains `$\pm 5-15$`, which Python reports as
> `SyntaxWarning: invalid escape sequence '\p'`. Tests still pass. Left untouched to avoid
> unrelated edits.

---

## 4. New regression tests (`tests/unit/test_phase23b_imagery_integrity.py`)

| Test class / test | Asserts |
|---|---|
| `TestNoFabricatedCoordinates.test_default_adapter_never_fabricates_geography` | No catalogue entry has coordinates; every local entry is `is_demo=True`. |
| `...test_default_adapter_returns_unmatched_for_real_route` | Default (real) mode yields `UNMATCHED`, no images. |
| `...test_demo_mode_labels_imagery_as_demo_and_discloses` | Demo images flagged `is_demo`, `coordinates=None`, disclosure limitations present. |
| `...test_default_and_demo_adapters_differ_on_same_segment` | Default unmatched vs explicit demo surfaced. |
| `TestMapillaryAuthFailure.test_401_never_uses_unrelated_fallback` | 401 → `INACCESSIBLE`; fallback called **0** times. |
| `...test_403_never_uses_unrelated_fallback` | 403 → `INACCESSIBLE`; fallback not called. |
| `...test_token_never_leaks_in_error_message` | Token absent from serialized result and message. |
| `TestCrossSegmentDeduplication.test_helper_dedups_same_image_hazard_across_segments` | Duplicate removed; aggregate reduced; disclosure added. |
| `...test_helper_preserves_distinct_hazards` | Different boxes / images are preserved. |
| `...test_helper_keeps_hazards_without_image_id` | Unknown-identity hazards never silently dropped. |
| `...test_pipeline_counts_shared_image_once` | End-to-end `_analyze_route`: `hazards_total == 1`, 1 hazard. |
| `TestPointToSegmentDistance.*` | Mid-edge match; on-line ≈ 0; outside radius rejected; empty/single/degenerate edges. |
| `TestCoverageHonesty.test_partial_coverage_never_scores_missing_segment` | `insufficient_coverage`; missing segment score `None`, suppressed. |
| `TestSecretHygiene.*` | Token absent from `to_safe_dict`, `repr`, `/api/health`, `/api/config`. |

All tests are hermetic: injected fake HTTP/providers/detectors, no token, no network, no YOLO
load.

---

## 4.1 Required regression coverage mapping

| Requirement | Test(s) |
|---|---|
| No fabricated geographic coordinates | `TestNoFabricatedCoordinates.*` |
| Demo imagery explicitly demo/unmatched | `test_demo_mode_labels_...`, `test_default_and_demo_...` |
| Mapillary 401/403 never silently substitutes | `TestMapillaryAuthFailure.*` |
| Same image ID counted once across adjacent segments | `TestCrossSegmentDeduplication.*` |
| Point-to-segment distance + edge cases | `TestPointToSegmentDistance.*` |
| Partial/missing coverage honest | `TestCoverageHonesty.*` |
| Token never in settings/API/logs | `TestSecretHygiene.*`, `test_token_never_leaks_...` |

---

## 5. Limitations / notes

- **Live Mapillary remains unexercised.** No `.env` and no token were created; the 401/403
  path was validated with an injected failing HTTP client only. No claim is made that live
  imagery works (Rule 14, 20).
- **Demo mode is opt-in and off by default.** Even when enabled, demo frames are labelled and
  disclosed and are never geographically matched; they remain unsuitable as real evidence.
- **Attribution/provenance (audit C5) and bbox-size guard (C6) were NOT in scope** for this
  phase and remain open.
- **De-dup identity** relies on a stable `image_id` and bounding-box overlap; hazards with no
  `image_id` cannot be identified and are deliberately retained rather than dropped.
- The pre-existing `matcher.py` `SyntaxWarning` (`\p` in a docstring) is non-failing and
  untouched.
- The routing/geocoding/LLM behaviour is unchanged.

---

## 6. Dataset & checkpoint integrity statement

This phase performed **no training, no downloads, no dataset modification and no checkpoint
modification**. `git status` before and after shows the same pre-existing uncommitted files
plus only the files listed in §2. No file under `models/` or the datasets was touched. No
`.env` was created and no token/credential was read, stored, printed or logged.

---

## 7. Honesty statement

All results in this report were produced by the commands shown and recorded as **[VERIFIED]**.
The full suite passed **148/148** tests after the change (baseline 128/128). No metric, image
availability or live-service behaviour is claimed beyond what was executed. The previously
reported defects (fixed-coordinate fallback, auth-failure substitution, unimplemented
de-duplication, point-to-vertex matcher) are now addressed in code and covered by tests; any
remaining gaps are listed in §5.
