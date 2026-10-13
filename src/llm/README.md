# SafeRoute AI — Grounded LLM Explanation Layer (`src.llm`)

> **Module Version:** `llm-v1`
> **Phase ID:** PHASE_17
> **Governing rules:** master_rules.md Rules 7, 12, 14, 16, 19; TRD §13, ARCHITECTURE §9.

---

## 1. Purpose

Explain **verified backend results** in natural language. The LLM **explains only**: it
must never compute or alter scores/ranking, nor invent routes, hazards, facilities or
measurements (Rules 7, 12).

## 2. Input boundary (verified data only)

The service receives a payload containing only backend-verified data:
`analysis_id, model_version, config_hash, routes[] (route_id, route_score, status,
coverage, hazards[]), recommendation, limitations`.

## 3. Output schema

`ExplanationResult`: `analysis_id, explanation, referenced_routes, referenced_hazards,
disclosures, source` where `source` is `"ollama"` or `"fallback"`.

## 4. Controls

- **Schema validation** — malformed model output is rejected.
- **Entity grounding** — every referenced route/hazard must exist in the input, else the
  response is rejected and the fallback is used.
- **Prompt-injection resistance** — user text is passed as *data*, never instructions;
  the model cannot trigger state-mutating actions.
- **No scores** — the LLM never emits or changes a score (engine owns scores, Rule 7).

## 5. Fallback

When Ollama is unavailable, disabled, or its output is rejected, a deterministic
template explanation is generated **only** from verified data, with `source="fallback"`.
The UI must mark fallback explanations.

## 6. Configuration (Ollama, optional)

Ollama is **disabled by default** and requires explicit approval before use (Rule 19).
Enable by constructing `GroundedExplanationService(base_url="http://localhost:11434",
model="<approved>", enabled=True)`. No model is downloaded automatically.

## 7. Tests

```powershell
.\.venv\Scripts\python.exe -m unittest tests.unit.test_llm_explainer -v
```
Covers: fallback path, grounding rejection of unknown entities, injection attempt,
and the no-score rule.

## 8. Limitations

- Without an approved local model, explanations come from the deterministic fallback.
- Explanations summarise verified data; they are not safety guarantees.
