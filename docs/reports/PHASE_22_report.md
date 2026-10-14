# PHASE 22 — Fix Critical Safety and Detection Bugs

> **Status:** COMPLETE · **Date:** 2026-10-14 · **Workspace:** `D:\New folder (3)`
> **Governing:** `master_rules.md` (Rules 5, 7, 9, 14, 20), `docs/TRAINING_RULES.md`,
> `docs/reports/COMPLETE_PROJECT_AUDIT.md` (§5 B1, B2).
> **Scope:** config + code fixes only. **No retraining, no checkpoint change, no
> dataset change.**

## 1. Root causes

- **B1 (threshold inconsistency).** `config/detection.yaml` ran the detector at
  `conf=0.15` while `config/hazard_severity.yaml` set the aggregator
  `confidence_threshold=0.25`. `HazardAggregator.process_image_detections`
  drops every detection `< 0.25`, so detections in `[0.15,0.25)` were **silently
  discarded** (measured: 20 of 56 detections, 36%).
- **B2 (misleading 100).** `DeterministicRiskEngine` returns
  `S = 100·exp(−λ·0)` = **100** whenever a covered segment has zero surviving
  hazards. Nothing distinguished *"imagery assessed, no hazard detected"* from
  *"road is safe"*, and no outcome/uncertainty was surfaced to API or UI.

## 2. Changes made (files + intent)

| File | Change |
|---|---|
| `config/detection.yaml` | `inference.conf` **0.15 → 0.25** (single policy; documented). |
| `config/hazard_severity.yaml` | Comment declares `confidence_threshold` the single authoritative policy (value 0.25 unchanged). |
| `src/config/thresholds.py` | **New.** `load_threshold_policy` + `assert_threshold_consistency` (single source of truth; fails loudly on divergence). |
| `src/config/__init__.py` | Export the new threshold API. |
| `src/api/pipeline.py` | Call the guard at construction; `_build_comparison` now includes `detection_outcome`, `hazards_total`, `safety_note` and an explicit "100 ≠ safe" comparison note. |
| `src/risk/schemas.py` | `RouteSafetyResult` gains `hazards_total`, `detection_outcome`, `safety_note` (serialized). |
| `src/risk/engine.py` | `score_route` computes the outcome/note (preserves the deterministic score formula). |
| `src/llm/explainer.py` | Deterministic fallback discloses `no_hazards_detected_not_proof_of_safety`. |
| `frontend/app.js` | New "Finding" column + recommended-route safety note + comparison note. |
| `tests/unit/test_threshold_consistency.py` | Equality test + loader + runtime-guard tests. |
| `tests/unit/test_detection_outcome.py` | **New.** Verifies the 5 outcomes and that 100 is labelled not-safe. |

## 3. Detection-outcome taxonomy (Task 2)

| `detection_outcome` | Meaning | Score |
|---|---|---|
| `hazards_detected` | Verified hazards on assessed segments | < 100 (per formula) |
| `no_hazards_detected` | Imagery **fully** assessed, none found — **NOT proof of safety** | 100 (labelled) |
| `insufficient_coverage` | Only part of the route assessable | score or None, disclosed |
| `detector_failed` | Detection/inference failed | None (`failed`) |
| `unassessed` | No assessable imagery | None (`unassessed`) |

The deterministic score formula is unchanged; the new fields add honesty, not
different math.

## 4. Verification (Task 3 — actual results)

- Focused: dry-run command
  `.\.venv\Scripts\python.exe -m unittest tests.unit.test_threshold_consistency tests.unit.test_detection_outcome tests.unit.test_detection tests.unit.test_hazard_aggregation tests.unit.test_risk_engine tests.unit.test_api tests.integration.test_end_to_end_api`
  → **Ran 63 tests … OK**.
- Full suite: `.\.venv\Scripts\python.exe -m unittest discover -s tests -t .`
  → **Ran 128 tests … OK** (previously 119 with 1 failure).
- E2E pipeline check: zero-hazard routes now return
  `detection_outcome=insufficient_coverage` (half-imagery case) with the
  comparison note present and the safety disclosure in the explanation.
- `test_threshold_consistency` now **PASSES** (0.15→0.25 aligned).

## 5. Remaining risks / not addressed here

- Detector **accuracy** is still low (not a bug; needs data/model work).
- Live Mapillary imagery and Ollama remain **BLOCKED** (no token/runtime).
- Security gaps (auth, rate limiting, CORS) are out of scope for PHASE_22.
- B3 (demo imagery fallback anchoring) and B5 (double letterbox) remain open (P1/P2).

## 6. Next recommended phase

**PHASE 23 — Imagery & threshold hardening**: wire a real imagery source
(Mapillary token) and remove the fixed-point fallback (B3); add API
auth/rate-limiting (P1); then evaluate v2 vs v1 on the held-out test set and only
promote if better.

