# SafeRoute AI — Architecture Document

> **Project:** SafeRoute AI — Intelligent Road Safety Navigation System
> **Workspace:** `D:\New folder (3)`
> **Status:** Draft — pending approval
> **Version:** 0.1
> **Date:** 2026-10-11
> **Companion rules:** [`../master_rules.md`](../master_rules.md) (authoritative)
> **Companion documents:** [`PRD.md`](./PRD.md) · [`TRD.md`](./TRD.md) · *(planned)* `TRAINING_RULES.md`

This document is subordinate to `master_rules.md`, `docs\PRD.md` and `docs\TRD.md`. Where
any conflict arises, `master_rules.md` prevails and the conflict must be raised and resolved
explicitly — never silently overridden.

**Evidence convention:**

- **[VERIFIED]** — observed fact confirmed inside the workspace or by a read-only system query.
- **[PROPOSED]** — recommended design; **not implemented, installed, trained or tested**.
- **[UNKNOWN]** — requires a decision, verification or asset that does not yet exist.

**Current verified state [VERIFIED]:** the workspace contains only `master_rules.md`,
`docs\PRD.md` and `docs\TRD.md`. There is **no** source code, environment, dataset, model
weights, backend, frontend, database, imagery or integration. **Every component described
below is proposed architecture, not an implemented system.**

---

## 1. Architecture overview

**Purpose.** SafeRoute AI compares the routes a routing provider actually returns for a
given destination, assessing road hazards along those routes using permitted imagery and a
YOLO11 detector, computing a deterministic hazard-risk score, and explaining verified
results through a grounded LLM. Its defining principle is **evidence honesty**: missing or
insufficient evidence is disclosed as *unknown/unassessed*, never treated as proof of a
safe road.

**Major components (all [PROPOSED]):**

| # | Component | Responsibility |
|---|---|---|
| 1 | React frontend | Destination input; presentation of routes, scores, coverage, evidence, facilities (separate) and explanations. |
| 2 | FastAPI backend | Orchestration and HTTP API; validates input; coordinates adapters and services. |
| 3 | Routing adapter | Fetch actual route alternatives, geometry and segment metadata behind a provider-independent interface. |
| 4 | Imagery adapter | Retrieve imagery only from permitted sources; record provenance and availability. |
| 5 | OpenCV pipeline | Image validation, deterministic preprocessing, visualisation, structured output. |
| 6 | YOLO11 detector | Detect supported road-hazard classes; emit structured detections. |
| 7 | Hazard aggregation service | Apply severity policy, confidence thresholds and de-duplication to detections. |
| 8 | Deterministic Risk Engine | Compute segment/route hazard-risk scores from verified evidence + coverage. |
| 9 | Facility lookup service | Retrieve nearby facilities (kept separate from hazard score). |
| 10 | Route-ranking service | Order routes and select a recommendation from deterministic results. |
| 11 | LLM explanation service (Ollama) | Explain verified backend results; never compute scores or invent facts. |
| 12 | MySQL persistence | Store searches, routes, segments, imagery refs, detections, model versions, scores, analysis history. |
| 13 | Logging & error handling | Structured, secret-free logs; explicit error and status propagation. |

**Data flow (summary).** User → React → FastAPI → routing adapter → routes + segmentation →
imagery adapter (permitted sources) → OpenCV preprocessing/quality checks → YOLO11
inference → hazard aggregation/severity → deterministic risk engine → route comparison and
recommendation → grounded LLM explanation via Ollama → React comparison interface.
Error and missing-data branches run alongside the happy path and produce
`unknown/unassessed/failed` statuses rather than a safe assumption.

**Proposed vs implemented.** *Proposed:* everything listed above. *Implemented:* nothing.

---

## 2. System architecture diagram

```mermaid
flowchart TD
    U[USER] --> FE[React Frontend]
    FE -->|destination / origin| API[FastAPI Backend]

    API --> RT[Routing Adapter]
    RT -->|provider call| RP[(Routing Provider<br/>UNRESOLVED / to be selected)]
    RP -->|routes actually returned| RTS[Route Alternatives<br/>+ Segmentation]
    RP -.->|fewer than 4 routes| FEW[Show only routes returned]
    RP -.->|request fails / timeout| RERR[Mark FAILED<br/>surface error]

    RTS --> IMG[Permitted Imagery Acquisition<br/>Imagery Adapter]
    IMG -->|permitted sources only| SRC[(Imagery Source<br/>UNRESOLVED<br/>terms must be reviewed)]
    IMG -.->|imagery unavailable / stale| UNK[Segment = UNKNOWN / UNASSESSED]
    SRC --> CV[OpenCV Pipeline<br/>validation + preprocessing]
    IMG --> CV

    CV -.->|corrupt / unsupported / low quality| IMGERR[Mark image FAILED<br/>not treated as clean]
    CV --> YOLO[YOLO11 Inference]

    YOLO -.->|missing checkpoint / inference error| YERR[Mark inference FAILED]
    YOLO --> AGG[Hazard Aggregation<br/>+ Severity Policy]

    AGG --> RISK[Deterministic Risk Engine<br/>S_i = 100 * exp(-lambda * H_i)]
    UNK --> RISK
    IMGERR --> RISK
    YERR --> RISK
    RISK --> CMP[Route Comparison<br/>+ Recommendation]
    FEW --> CMP
    RERR --> CMP

    CMP --> LLM[Grounded LLM Explanation<br/>via Ollama]
    LLM -.->|Ollama unavailable| FB[Deterministic fallback message]
    LLM --> FE2[React Route-Comparison Interface]
    FB --> FE2
    CMP --> FE2

    FAC[(Facility Lookup<br/>separate concern)] --> FE2
    RISK --- DB[(MySQL Persistence)]
    FE2 --- DB

    classDef unknown fill:#ffe9b3,stroke:#a67c00,color:#000;
    classDef err fill:#ffd6d6,stroke:#a30000,color:#000;
    class UNK,FEW,RTS unknown;
    class IMGERR,YERR,RERR err;
```

**Reading the error / missing-data paths.** Unavailable, stale, corrupt, unmatched or
failed imagery **never** becomes "safe". It flows into the Risk Engine as an
`unknown/unassessed/failed` status that is disclosable and that prevents an unassessed route
being presented as safe (Rule 9).

---

## 3. Component responsibilities

### React frontend
Renders destination input, route alternatives (only those returned), safety scores with
their basis, coverage indicators, hazard evidence, facilities (separately), explanations,
loading and error states. Displays coverage/limitations prominently. Contains **no** scoring
logic.

### FastAPI API layer
Owns request validation, orchestration, status propagation and response schemas. Delegates
to adapters/services; does not itself compute hazards or scores.

### Routing adapter
Provider-independent `get_routes` / `get_route_geometry` / `get_segment_metadata`. Returns
only genuinely returned routes; maps provider errors to explicit failure statuses.

### Imagery adapter
Provider-independent `get_imagery` from **permitted sources only**. Records source,
provenance, timestamps and availability; returns `Unavailable` when imagery is missing,
stale or disallowed.

### OpenCV pipeline
Validates decodability/emptiness, applies the single documented preprocessing pipeline,
prepares inference input, visualises detections, emits structured quality results. Preserves
originals; writes artefacts to safe workspace paths.

### YOLO11 detector
Loads the approved checkpoint and returns structured detections (class, confidence, bbox,
IDs, status). Reports only supported/trained classes. **Never** computes safety scores.

### Hazard aggregation service
Applies the documented severity policy, configurable confidence threshold and
de-duplication to produce hazard records. No LLM involvement.

### Risk Engine
The **only** component that computes safety scores (Rule 7). Consumes verified detections +
coverage + segment information; emits segment and route scores with coverage status.
Deterministic and unit-testable. Independent of the LLM and of facilities.

### Facility lookup service
Retrieves nearby facilities (hospitals, pharmacies, restaurants, hotels, petrol pumps,
police stations) from a permitted provider. **Kept separate from the hazard score** (Rule 11).

### Route-ranking service
Orders routes and selects the recommendation using deterministic scores + disclosed
coverage. The LLM never overrides this.

### Ollama / LLM explanation service
Receives **only verified backend results** and returns a constrained, schema-validated
explanation. **Must never** calculate the risk score, invent facts, or alter deterministic
route ranking (Rules 7, 12).

### MySQL persistence
Stores application and analysis data (entities in §10). No more sensitive data than
necessary.

### Logging and error handling
Structured, secret-free logs; explicit assessed/partial/unassessed/failed statuses; graceful
degradation.

---

## 4. Data-flow contracts

> All JSON below is **[PROPOSED] contracts**, not existing APIs. Field names/values are
> illustrative placeholders.

### Route alternative
```json
{
  "route_id": "r1",
  "provider": "<selected-or-unresolved>",
  "summary": "…",
  "distance_m": 0,
  "duration_s": 0,
  "geometry_ref": "geom-r1",
  "segments": ["seg-r1-0", "seg-r1-1"]
}
```

### Route segment
```json
{
  "segment_id": "seg-r1-0",
  "route_id": "r1",
  "seq": 0,
  "length_m": 0,
  "geometry_ref": "geom-seg-r1-0",
  "imagery_refs": ["img-…"],
  "coverage_status": "assessed"
}
```

### Hazard detection
```json
{
  "model_version": "saferoute-yolo11-v1",
  "image_id": "img-…",
  "route_id": "r1",
  "segment_id": "seg-r1-0",
  "hazard_class": "pothole",
  "confidence": 0.0,
  "bbox_xyxy": [0, 0, 0, 0],
  "bbox_norm": [0.0, 0.0, 0.0, 0.0],
  "severity": 0.0,
  "status": "assessed",
  "error": null
}
```

### Segment assessment
```json
{
  "segment_id": "seg-r1-0",
  "model_version": "saferoute-yolo11-v1",
  "coverage": { "images_total": 0, "images_used": 0, "fraction": 0.0 },
  "detections": [],
  "aggregate_hazard": 0.0,
  "segment_score": 0.0,
  "status": "assessed",
  "limitations": []
}
```
*(`status` ∈ `assessed` | `partially_assessed` | `unassessed` | `failed`.)*

### Route safety result
```json
{
  "route_id": "r1",
  "model_version": "saferoute-yolo11-v1",
  "route_score": 0.0,
  "coverage": { "assessed_segments": 0, "total_segments": 0, "fraction": 0.0 },
  "config_hash": "…",
  "status": "assessed",
  "limitations": []
}
```

### LLM explanation — input / output
```json
// INPUT (verified backend data only)
{
  "routes": [ { "route_id": "r1", "route_score": 0.0, "status": "assessed" } ],
  "coverage": [ { "route_id": "r1", "fraction": 0.0 } ],
  "scoring_factors": { "config_hash": "…", "lambda": null, "H_definition": null },
  "limitations": ["…"]
}
```
```json
// OUTPUT (schema-validated, no new facts)
{
  "explanation": "…",
  "referenced_routes": ["r1"],
  "referenced_hazards": [],
  "disclosures": ["…"],
  "source": "ollama | fallback"
}
```
Output is rejected if it references entities not present in the input (§9).

---

## 5. YOLO11 model lifecycle

1. **Dataset provenance & licence review** — document source, licence, permitted use before
   any training (Rules 15, 17). No dataset currently exists [VERIFIED].
2. **Annotation & class-ID validation** — confirm format (YOLO/COCO/VOC), class order and
   IDs against actual files; reconcile with the proposed classes in TRD §4.2. No silent
   relabelling (Rule 15).
3. **Train/validation/test separation** — verify splits; detect cross-split leakage.
4. **Training & evaluation** — baseline-first (YOLO11n) with recorded config/seed/versions;
   metrics measured only, never fabricated (Rule 14).
5. **Checkpoint storage** — under `models\training\saferoute-yolo11-v1\` inside the
   workspace (Rule 1). **No checkpoint currently exists.**
6. **Model versioning** — canonical identifier **`saferoute-yolo11-v1`**; model size
   (n/s/m) and checkpoint path recorded **separately** as metadata so the version label is
   stable across size experiments.
7. **Model loading & inference** — the detector loads the approved checkpoint for inference;
   missing checkpoint → explicit failure status, never a silent fallback to a different
   model.
8. **Evaluation & rollback** — a newer model replaces the serving checkpoint only after it
   passes evaluation; the previous validated model remains available for rollback.

**Explicitly not claimed:** no model, pretrained weight or checkpoint exists in the
workspace. Training is gated on dataset + CUDA verification and explicit approval.

---

## 6. OpenCV and image lifecycle

**Flow:** acquire → validate → preprocess (single documented pipeline) → prepare inference
input → YOLO11 inference → visualise → structured output.

| Stage | Behaviour |
|---|---|
| Acquire | From permitted sources only (Rule 8); record provenance/timestamp. |
| Validate | Decode check; reject null/empty/unreadable/unsupported files. |
| Preprocess | One versioned pipeline shared with training where applicable (Rule 6); consistent colour handling; letterbox for inference. |
| Prepare input | Avoid duplicating preprocessing Ultralytics already performs. |
| Visualise | Draw boxes/labels/confidences onto **copies**; never overwrite originals. |
| Structured output | Emit quality status + detections with IDs and error info. |

**Failure behaviour:**
- **Corrupt / unsupported / unreadable** → marked `failed`; excluded as evidence; disclosed.
- **Empty / zero-byte** → marked `failed`; disclosed.
- **Low quality** (e.g. severe blur/glare, defined by a documented, tested criterion) →
  flagged; may be excluded with disclosure.
- **Missing imagery** → segment `unknown/unassessed`; **never** treated as clean or safe
  (Rule 9).
- **Optional CLAHE** → applied only if evaluated; never default-on (Rule 6).

**Limitation:** a single uncalibrated monocular image **cannot** reliably yield physical
pothole depth or real-world dimensions. The system must not claim metric depth/area.

---

## 7. Deterministic risk engine

Candidate score (from TRD §9):

```
S_i = 100 × exp(-λ × H_i)
```

- `S_i` — hazard-risk score for unit `i` (higher = safer).
- `H_i` — hazard aggregation for unit `i` — **definition NOT YET SPECIFIED**.
- `λ` — scaling parameter — **NOT YET TUNED**.

**Intended roles:**
- **Segment risk** — computed per segment from aggregated detections, severities and the
  covered fraction of the segment.
- **Route aggregation** — combine segment risks weighted by segment length/extent and
  coverage.
- **Severity** — from the documented severity policy (TRD §8), never LLM judgement.
- **Confidence** — filters/weights detections via a configured threshold.
- **Segment length** — normalises hazard density so long segments are not penalised purely
  for length.
- **Coverage** — reported alongside any score; insufficient coverage is disclosed and may
  prevent a "safe" verdict.

**Open items:** `H_i`, `λ`, normalisation and the aggregation function **require documented
validation before implementation**. No score may be presented as calibrated until then.

**De-duplication:** the same physical hazard must not be counted repeatedly across adjacent
segments where reliable identity matching is possible (e.g. overlapping coordinates/imagery
or stable hazard identity).

**Missing imagery is never zero risk.** Absence of evidence is not evidence of safety.

---

## 8. Routing, imagery and facility providers

**Provider-independent interfaces [PROPOSED]:**
- Routing: `get_routes(origin, destination, options)`,
  `get_route_geometry(route_id)`, `get_segment_metadata(route_id)`.
- Imagery: `get_imagery(segment_id, permitted_source)`.
- Facilities: `get_nearby_facilities(location, radius, categories)`.

This isolates providers so one can be replaced without rewriting the application.

**Unresolved decisions [UNKNOWN]:**
- Routing provider selection (cost, coverage, terms).
- Permitted imagery source and its licence.
- API credentials/secret management approach.
- Segment-to-image matching method and accuracy.
- Facility provider and confirmation that facilities stay separate (Rule 11).

**Guardrail:** **Do not assume Google Maps permits automated imagery extraction or reuse.**
No endpoint, permission, dataset or coordinate-matching capability may be invented; the
provider record remains *unresolved* until access and usage terms are reviewed and approved
(Rule 8).

---

## 9. LLM boundary and prompt security

**Boundary.** The LLM receives **only verified backend results** (§4) and returns a
**constrained** explanation. It does **not** see raw user text as instructions to compute
anything, and it cannot alter backend state.

**The LLM must NOT:**
- Invent hazards or facility information.
- Estimate unobserved road conditions.
- Calculate or change safety scores.
- Override the route-ranking service.
- Describe an unassessed route as safe.

**Controls:**
- **Schema validation** of every response (`explanation`, `referenced_routes`,
  `referenced_hazards`, `disclosures`, `source`).
- **Entity grounding check** — any referenced route/hazard/facility not present in the
  backend input is rejected.
- **Prompt-injection resistance** — user text is treated as data, never as system
  instruction; instructions from content/imagery text are ignored; the LLM cannot trigger
  tool calls that mutate state.
- **Ollama-unavailable fallback** — a deterministic, template-generated message built only
  from verified backend data is returned instead; the UI marks explanations as *generated
  from verified data* and flags fallback use.

---

## 10. Database and persistence

**[PROPOSED]** MySQL entities/relationships. **The database and migrations are NOT created
in this phase.** Store no more sensitive data than necessary; prefer no personal data
(Rule 13).

```
users (id, created_at, prefs_json)
  └─< searches (id, user_id, origin, destination, created_at)
        └─< routes (id, search_id, provider, summary, distance_m, duration_s)
              └─< route_segments (id, route_id, seq, length_m, geometry_ref)
                    └─< imagery_refs (id, segment_id, source, captured_at, licence,
                                      path_or_url, status)
                    └─< hazard_detections (id, segment_id, image_id, model_version_id,
                                           hazard_class, confidence, bbox_json, severity, status)
model_versions (id, name, size, checkpoint_path, trained_at, metrics_json)
scores (id, route_id, model_version_id, config_hash, S, H, coverage, status, computed_at)
analysis_history (id, search_id, created_at, result_json, status)
```

A **search** has many **routes**; a **route** has many **segments**; a **segment** has many
**imagery_refs** and **hazard_detections**; **scores** reference a route, a model version and
a config hash for reproducibility.

---

## 11. Security and operational boundaries

- **Secret management:** secrets only in local, uncommitted `.env`; `.env.example` documents
  names (Rule 13).
- **Input validation:** types, ranges, string bounds on all endpoints.
- **Upload restrictions:** allowed types/sizes; storage inside the workspace; no path
  traversal.
- **API timeouts & retries:** bounded, with backoff, for routing/imagery/LLM calls.
- **Rate limits:** per-client and per-provider where applicable.
- **Privacy:** minimise stored personal data; no personal data in logs.
- **Logging:** structured, secret-free, inside `logs\`.
- **Resource limits:** cap concurrent analyses and image sizes to fit 8 GB VRAM / 16 GB RAM.
- **Graceful failures:** unassessed/failed states are explicit and recoverable.
- **Isolation:** **all project artifacts and runtime outputs must remain under
  `D:\New folder (3)`** (Rule 1).

---

## 12. Deployment and runtime

**[PROPOSED]** local development setup only. **All components are proposed until verified.**

| Component | Proposed setup | Status |
|---|---|---|
| Python venv | workspace-local `.venv` (Python 3.12) | Not created |
| Backend | FastAPI served locally (e.g. Uvicorn) | Not created |
| Frontend | React dev server | Not created |
| MySQL | Local server + schema/migrations | Not created |
| Ollama | Local LLM runtime | Not installed |
| CUDA PyTorch | CUDA-enabled build verified against the GPU/driver | Not installed |

No deployment, container or external hosting is proposed in this phase. Any install,
download or credential creation requires explicit approval (Rule 19).

---

## 13. Architecture decisions and open questions

**Decisions recorded:**
- Deterministic risk engine is the sole owner of safety scores; LLM explains only.
- Facilities remain separate from the hazard score (no facility-weighted score without an
  approved requirements change).
- Missing imagery → unknown/unassessed; never implies safety.
- Provider-independent routing/imagery/facility interfaces.
- Model identifier `saferoute-yolo11-v1`, size recorded separately.
- Single shared, versioned OpenCV preprocessing pipeline.

**Open questions / unresolved [UNKNOWN]:** routing provider; permitted imagery source &
licence; credentials management; segment-to-image matching; `H_i` and `λ`; model size &
schedule; Ollama model choice; facility provider; deadline scope; dataset source/licence.

**Assumptions (to validate):** dataset and CUDA environment will be provided; hardware is
adequate for the chosen YOLO11 size.

**Risks:** no dataset; no approved imagery; CPU-only PyTorch; provider/ToS uncertainty;
class-coverage gaps; low free RAM; deadline pressure.

**Known documentation inconsistency (to resolve, not silently changed):** `PRD.md` §5 writes
the model identifier as `safroute-yolo11-v1`, whereas `TRD.md` §5.6 and this step's
instruction use `saferoute-yolo11-v1`. This document follows the instruction
(`saferoute-yolo11-v1`); the discrepancy should be reconciled by an approved documentation
update rather than an ad-hoc edit.

**No provider credentials and no dataset availability are assumed anywhere in this document.**

---

## 14. Implementation order

Dependency-aware sequence; each step gated on explicit approval and verified before the
next (Rules 3, 19). Earlier integration tests are allowed **only** where prerequisites
already exist.

1. **Documentation and environment checks** — finalise docs; inspect environment (no
   installs).
2. **Dataset discovery and validation** — obtain/approve a workspace-local dataset; run the
   integrity audit (TRD §4).
3. **CUDA-enabled environment verification** — create `.venv`; verify CUDA PyTorch, GPU,
   VRAM, RAM, disk (fresh; the audit found CPU-only torch).
4. **YOLO11 baseline and evaluation** — baseline-first (YOLO11n); measure metrics; isolate
   test set.
5. **OpenCV inference pipeline** — shared preprocessing, structured detections.
6. **Hazard aggregation and deterministic risk engine** — severity policy, `H_i`, `λ`
   documented and validated.
7. **Routing and permitted imagery integration** — provider behind interfaces; edge cases.
8. **Backend and persistence** — API + MySQL.
9. **Grounded LLM explanation** — constrained, with fallback.
10. **Frontend integration and end-to-end testing** — wire UI; run full E2E + negative tests.

**Blocking note:** steps 4 onward **cannot** proceed without steps 2–3. Steps 6–10 cannot
present meaningful results without a trained model and permitted imagery. A small, honest
demonstration is prioritised over advanced features.

---

## Quality rules acknowledgement

This document distinguishes **[VERIFIED]** facts from **[PROPOSED]** architecture and
**[UNKNOWN]** items; claims nothing is implemented, installed, trained or tested; defers to
`master_rules.md` on conflict; adds no files, directories, packages, datasets or model
weights; and does not silently alter approved PRD/TRD decisions.
