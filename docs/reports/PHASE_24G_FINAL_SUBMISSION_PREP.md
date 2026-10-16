# SafeRoute AI — PHASE 24G: Final-Submission Preparation

> **Phase:** PHASE 24G — final-submission preparation following the v2 checkpoint
> promotion noted in `config/detection.yaml`.
> **Date executed:** 2026-10-16 (UTC) · **Workspace:** `D:\New folder (3)` · **Branch:** `main`
> **Mode:** verification + two small, directly-justified fixes. No retraining, no
> checkpoint replacement, no commit/push/deploy.
> **Governing rules:** `master_rules.md` 1, 2, 7, 9, 12, 13, 14, 17, 18, 19, 20.

---

## 1. Priority 1 — LLM (Ollama) configuration

**Problem.** `config/app.yaml` requested `llm.model: "llama3.2"`, but the locally
installed Ollama tags (verified via `GET /api/tags` / `ollama list`) are only:

| Installed tag | Size |
|---|---|
| `llama3:latest` | 4.66 GB |
| `gemma2:2b` | 1.63 GB |

`llama3.2` was **not installed**, so every live explanation silently fell back to
the deterministic explanation (`source: "fallback"`).

**Smallest justified change (permitted by the rules — local, non-secret, no
download/install):** point the configured model at an installed tag.

- `config/app.yaml`: `llm.model: "llama3.2"` → `"llama3:latest"`.
  `llama3:latest` was chosen as the nearest installed match to the intended
  model and produced the most complete grounded explanation in testing.

**Companion fix required for the live pipeline (directly justified, minimal).**
`SafetyAnalysisPipeline.analyze()` passes the *entire* analysis record to the
explainer. That record includes full route geometry and per-segment/imagery
detail (~130 KB). Both installed models reproduced this failure 3/3 times on the
full payload and succeeded 3/3 times on a compact representative payload:

| Model | Full record (~130 KB) | Compact payload |
|---|---|---|
| `llama3:latest` | fallback ×3 | ollama ×3 |
| `gemma2:2b` | fallback ×3 | ollama ×3 |

With the huge prompt the model echoed an input fragment (e.g. an imagery-status
object) instead of the required schema, so grounding rejected it and the service
fell back. Fix: `src/llm/explainer.py` now sends a compact projection of the
**same verified data** to Ollama (`_project_for_prompt`), while
`_parse_and_ground` still validates the reply against the full payload (Rule 12).
No field is invented; the scoring/versioning metadata is untouched.

**Verification (live HTTP, `llama3:latest`):** `POST /api/analyze` now returns
`explanation.source = "ollama"` with `referenced_routes` restricted to routes in
the input.

**Remaining LLM limitations (honest):**
- Code-level fallback literals still say `"llama3.2"` in
  `src/config/settings.py` (`Settings.llm_model`, `load_settings`) and
  `src/llm/explainer.py` (constructor default). The runtime uses
  `config/app.yaml`, so behaviour is correct, but the defaults are stale.
- The first request after a cold Ollama start can still exceed the 30 s timeout.
- The LLM occasionally phrases the all-unassessed case as "no hazards were
  detected". The structured record remains authoritative (`status: unassessed`,
  `route_score: null`, no recommendation), so Rule 9 is not violated, but the
  deterministic fallback wording is more careful.

---

## 2. Priority 2 — End-to-end demo

**Available local imagery.** `logs/evaluation/qualitative_samples/*.jpg` (20 real
dashcam frames). These have **no verified geographic coordinates** and are
indexed by `PermittedImageryAdapter` as demo entries (PHASE_23B). No Mapillary
token is configured, so live geographically-matched imagery is unavailable and
was **not** acquired.

**Demo A — honest default (`/api/analyze`, live OSRM, demo mode OFF).**
Bengaluru coords → 2 real OSRM routes.

| Check | Result |
|---|---|
| Imagery matched | **No** — all 79 segments `unmatched` |
| Hazards detected | 0 |
| Risk assessed | **No** — both routes `unassessed`, `route_score null`, ranking `[]` |
| Explanation | Generated, `source = ollama` (after the fix) |
| Safe claim | None — no route presented as safe (Rule 9) |

**Demo B — explicit imagery demo mode ON (clearly labelled, non-geographic).**
Short live OSRM route (1 route, 6 segments). Imagery returned but disclosed
`demo_imagery_not_geographically_matched` / `demo_imagery_not_route_evidence`.

| Check | Result |
|---|---|
| Imagery matched | **No** (demo frames only; disclosure present) |
| Hazards detected | 16 |
| Risk assessed | Yes — route score 82.9, coverage 1.0, `assessed` |
| Explanation | `source = ollama` |
| Caveat | Demonstrates the machinery only; **not** a real route-safety claim |

**Real-image vision chain (detector → aggregator → risk → LLM), CPU.** 20 local
frames → 16 hazards (14 crack, 2 pothole) → 2 assessed segments → route score
8.46 → Ollama explanation referencing `crack`, `pothole`. Imagery is real but
**not** geographically matched to a route (Rule 9 / Rule 20 disclosure applies).

---

## 3. Priority 3 — Known version discrepancy (recorded, NOT changed)

Default detection and the pipeline report **v2**, while the deterministic risk
layer still reports the static **v1** configuration pin:

| Layer | Source | `model_version` |
|---|---|---|
| Detector (default) | `config/detection.yaml` → v2 checkpoint | `saferoute-yolo11-v2` |
| Pipeline record | `src/api/pipeline.py MODEL_VERSION` | `saferoute-yolo11-v2` |
| Hazard records | detector's `ImageDetectionResult` | `saferoute-yolo11-v2` |
| Segment scores | `config/risk_engine.yaml` metadata pin | `saferoute-yolo11-v1` |
| Route scores | `config/risk_engine.yaml` metadata pin | `saferoute-yolo11-v1` |
| Segment assessments | `config/hazard_severity.yaml` metadata pin | `saferoute-yolo11-v1` |

**Root cause:** `config/risk_engine.yaml` and `config/hazard_severity.yaml` retain
`metadata.model_version: "saferoute-yolo11-v1"`, and
`src/risk/engine.py` / `src/risk/severity.py` read that static pin (fallback
literal also v1). These are independent of the promoted detection checkpoint.

**Evidence:** observed live in all three demo runs above
(`record.model_version = v2` alongside `route.model_version = v1` and
`segment_scores[*].model_version = v1`).

**Decision:** not changed. Per instructions, risk configuration metadata, risk
tests, and version-propagation behaviour are left untouched until an explicit,
documented basis for the change is approved. This section is that recorded basis
candidate; no edit was made.

---

## 4. Tests and workspace state

```powershell
# Focused (LLM, settings, API, both integration suites)
.\.venv\Scripts\python.exe -m unittest tests.unit.test_llm_explainer tests.unit.test_settings_env `
    tests.unit.test_api tests.integration.test_end_to_end_api tests.integration.test_end_to_end_pipeline -v
# -> Ran 32 tests ... OK  (exit 0)

# Full suite
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# -> Ran 148 tests ... OK  (exit 0)
```

Changed/added files this phase:

```
config/app.yaml                                 (modified: llm.model -> llama3:latest)
src/llm/explainer.py                            (modified: compact grounded prompt projection)
docs/reports/PHASE_24G_FINAL_SUBMISSION_PREP.md (new: this report)
```

No risk config, risk test, checkpoint, dataset, or split was modified. Nothing
was committed or pushed.
