# SafeRoute AI — PHASE 28: Live LLM Explanation Repair

> **Phase:** PHASE 28 — live LLM explanation failure (Phase 1 of the repair plan)
> **Date executed:** 2026-10-21 (UTC) · **Workspace:** `D:\New folder (3)` · **Branch:** `main`
> **Mode:** targeted repair of the explanation layer + tests + live verification.
> No retraining, no checkpoint replacement, no dependency install, no commit/push/deploy.
> **Governing rules:** `master_rules.md` 1, 2, 7, 9, 12, 13, 14, 17, 18, 19, 20.

---

## 1. Problem

Live route analyses returned `explanation.source = "fallback"` even though the
local Ollama server was running and reachable, and the configured 30 s timeout
was reported to expire occasionally. The frontend already rendered
`analysis.explanation` and its source label, so no frontend change was needed.

## 2. Root cause (reproduced, not assumed)

`src/llm/explainer.py` sent the **entire** verified hazard list of **every**
route to the model and relied on a soft prompt contract. With a long route the
prompt grew to ~140 KB, and the local model answered with the *wrong JSON
structure* — it simply continued the data instead of the contract. Grounding
rejected the reply, so the service silently degraded to the deterministic text.

Measured against the installed Ollama 0.40.6 (`llama3:latest`, 4.34 GB):

| Prompt | Bytes | Model reply | Result |
|---|---|---|---|
| Old projection, 880 hazards | 143,582 | `{"hazard_segments": [...]}` | **rejected → fallback** |
| Old projection, 880 hazards | 143,582 | `{"description": "..."}` | **rejected → fallback** |
| Old projection, 880 hazards | 143,582 | `{"rank": 1, "route_id": ...}` | **rejected → fallback** |
| Bounded projection + strict contract | 4,576 | correct 4-field object | **accepted → `ollama`** |

The old projection also lost the required fields entirely: the model echoed a
hazard/segment object instead of `explanation` / `referenced_routes` /
`referenced_hazards` / `disclosures`.

## 3. Changes (minimal, all in the explanation layer + configuration)

### `src/llm/explainer.py` (rewritten in place; fallback text unchanged)

1. **Bounded prompt projection.** Each route now carries
   `hazards_total` (exact count), `hazards_by_class` (exact per-class counts),
   a bounded `hazards_sample` (≤ 6, class-diverse, deterministic) and a
   `hazards_sample_note` that states the subset is *NOT exhaustive*. The
   comparison ranking's unbounded `hazard_segments` list became
   `hazard_segments_count` + a bounded `hazard_segments_sample`. A byte budget
   (`MAX_PROMPT_BYTES = 24_000`) halves the sample if a pathological payload
   still exceeds it. The exact totals are never dropped.
2. **Explicit output contract.** `SYSTEM_PROMPT` now names the four required
   fields, their types and the "representative subset" semantics, and the
   Ollama request asks for structured output via `format: OUTPUT_JSON_SCHEMA`.
   An HTTP 400 (older Ollama without JSON-schema support) retries once in
   plain `format: "json"` mode; a second failure still falls back.
3. **Stronger contract validation.** All four fields must be present and
   well-typed; unknown entity references are rejected as before.
4. **Grounding extended to the explanation TEXT** (the gap that let the old
   code accept a reply that quoted another route's distance as the recommended
   route's): invented route identifiers, invented safety scores, and safety or
   recommendation claims about routes the backend did not rank are rejected.
5. **Bounded timeout.** The service clamps the timeout to `[1.0, 300.0]` s, so
   a misconfigured `0` can no longer block forever.
6. **Diagnostics.** `GroundedExplanationService.last_error` records why a reply
   was rejected (diagnostic only; never surfaced as a user-facing claim).

### Configuration

| File | Change |
|---|---|
| `config/app.yaml` | `llm.timeout_seconds: 30.0 → 45.0` |
| `src/config/settings.py` | `llm_timeout_seconds` default `30.0 → 45.0` (dataclass + YAML fallback) |
| `.env.example` | documents `SAFEROUTE_LLM_TIMEOUT_SECONDS` |

### Explicitly **not** changed

Risk formulas, thresholds, YOLO11 weights, route eligibility, safety ranking,
facility scoring, hospital accessibility, incident analysis, database
architecture and the frontend. No dependencies installed, no provider/model
weight changes, nothing staged/committed/pushed.

## 4. Measurements

| Measurement | Value |
|---|---|
| Prompt payload, 880-hazard synthetic long trip | 143,582 B → **10,502 B** (13.7× smaller) |
| Prompt payload, live short route (`an-45424c01cd7e`, 36 hazards) | 9,201 B → **5,957 B** |
| Prompt payload, live long route (`an-48ffdc429fba`, 44 hazards) | 9,258 B → **3,400 B** |
| Ollama cold start (model load) | 7.19 s |
| Ollama warm generation, bounded prompt | 1.5 – 3.0 s |
| Live LLM call in-situ on the live analysis records | 2.44 s / 2.52 s |
| Configured timeout | 45 s (≈ 18× the measured warm latency) |

**Timeout justification.** The measured worst case is a ~7 s cold model load;
45 s keeps an order of magnitude of headroom for a model that is still loading
behind another queued request while remaining strictly bounded (and the
service clamps any value into `[1.0, 300.0]`). The 30 s value was not removed
as "unnecessary" — it was raised because the diagnosis reported expiry, and
the prompt reduction alone does not protect against a cold/queued model.

## 5. Tests

`tests/unit/test_llm_explainer.py` was rewritten (6 → 37 tests) covering:
valid JSON, malformed JSON, JSON array instead of object, missing fields
(each of the four), wrong field types, empty explanation, unknown route /
hazard references, fenced JSON, invented route id in the text, invented score,
safety claim about an unassessed route, naming a non-recommended route as
safest, `cannot_determine` naming a route, negated claims, bounded prompt
projection for a 1000-hazard payload, accurate totals, representative sample,
the structured-output request body, timeout → deterministic fallback,
transport error → fallback, wrong-structure reply → fallback, bounded timeout,
and reproducible deterministic fallback.

| Suite | Before | After |
|---|---|---|
| `tests.unit.test_llm_explainer` | 6 tests | **37 tests, OK** |
| `python -m unittest discover -s tests` | 229 tests, OK | **260 tests, OK** |

No test could not be run. `pytest` is **not** installed in `.venv`; the
project's documented runner is `unittest` (`README.md`).

## 6. Live verification

API started with `python -m src.api.app`; `GET /api/health` reported
`"llm": "ollama"`, `"live_llm": true`.

| Run | Route | Result |
|---|---|---|
| Short | MG Road → Koramangala (~3 km) | `source = "ollama"`, 36 hazards, 2 route ids referenced |
| Long | MG Road → Whitefield (~18 km) | `source = "ollama"`, 44 hazards, score 73.71 quoted correctly |

The frontend contract was verified by replaying `toAnalysisView()` from
`frontend/Frontend/project frontend/src/utils/backendRoutes.ts` against the
live API responses: `explanation` is populated, `explanationSource = "ollama"`,
and the panel label renders as `AI Explanation · source: ollama`. The built
bundle `frontend/assets/index-ChLfkaQi.js` already contains the
`explanationSource` render path, so no frontend change was required.

**A real browser was not used:** no browser-automation package is installed
and installing one is out of scope for this phase. The verification above
reproduces the exact mapping and label the panel renders from the same live
response.

## 7. Honest limitations

1. **Both live routes resolved to `cannot_determine`.** The Mapillary provider
   returns `captured_at = None` for every image, so freshness is unverifiable
   and the backend (correctly, Rule 9) refuses to recommend a route. The LLM
   explained this correctly. The *recommended-route* branch was therefore
   exercised live against Ollama directly (5/5 replies accepted, model naming
   the backend's recommended route) and in unit tests, but not through the
   public API in this environment.
2. **Claim binding is a heuristic.** A claim is bound to a route identifier by
   short proximity inside a clause, and a negation cancels a claim in the same
   clause. Some unsupported phrasings can slip through (e.g. a safety claim in
   a sentence that names no route at all, or a claim split across clauses);
   those are false *negatives* of the grounding check, i.e. the deterministic
   fallback is not triggered. The failure direction is "accept", never
   "invent".
3. **Score checking is keyword-anchored.** Only numbers directly attached to a
   score keyword ("score of X", "X/100", "scored X") or a comma-separated list
   after such a keyword are validated. A score quoted with no keyword nearby
   ("73.71") is not checked. Scores of exactly `0` and `100` are always allowed
   because they are legitimate endpoints of the 0–100 index.
4. **Route-id detection is pattern-based** (`rt-*`, `route_*`). A fabricated
   identifier that matches neither pattern is not detected in the text.
5. **The structured-output request needs Ollama ≥ 0.5.** On older servers the
   request is retried once in plain JSON mode, where the prompt contract
   (not the server) enforces the four fields; a non-conforming reply then
   falls back to the deterministic text.
6. **The 45 s timeout is a configuration value, not a guarantee.** A request
   that still exceeds it falls back to the deterministic explanation, which is
   the intended safe behaviour.

## 8. Files changed

| File | Change |
|---|---|
| `src/llm/explainer.py` | Bounded prompt projection, strict output contract, text grounding, bounded timeout, diagnostics |
| `tests/unit/test_llm_explainer.py` | Rewritten test suite (37 tests) |
| `config/app.yaml` | `llm.timeout_seconds: 45.0` |
| `src/config/settings.py` | `llm_timeout_seconds` default `45.0` |
| `.env.example` | documents `SAFEROUTE_LLM_TIMEOUT_SECONDS` |
| `docs/reports/PHASE_28_LLM_EXPLANATION_REPAIR.md` | this report |

Phase 2 is not started; it waits for explicit approval.
