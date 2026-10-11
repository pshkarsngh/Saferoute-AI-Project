# SafeRoute AI — Technical Requirements Document (TRD)

> **Project:** SafeRoute AI — Intelligent Road Safety Navigation System
> **Workspace:** `D:\New folder (3)`
> **Status:** Draft — pending approval
> **Version:** 0.1
> **Date:** 2026-10-11
> **Companion rules:** [`../master_rules.md`](../master_rules.md) (authoritative)
> **Companion documents:** [`PRD.md`](./PRD.md) · *(planned)* `ARCHITECTURE.md`, `TRAINING_RULES.md`

This TRD is subordinate to `master_rules.md` and elaborates the technical design for the
requirements in `PRD.md`. Where any conflict arises, `master_rules.md` prevails and the
conflict must be raised and resolved explicitly — never silently overridden.

**Evidence convention used throughout this document:**

- **[VERIFIED]** — observed fact confirmed inside the workspace or by a read-only system
  query during the audit.
- **[PROPOSED]** — recommended technical choice; **not installed, not implemented, not
  tested**.
- **[UNKNOWN]** — requires a decision, verification or asset that does not yet exist.

Nothing in this document should be read as a claim that any component is installed,
implemented, trained, integrated or tested.

**Current verified workspace state [VERIFIED]:** the workspace contains only
`master_rules.md` and `docs\PRD.md`. There is **no** dataset, model weights, virtual
environment, source code, backend, frontend, database or integration of any kind.

---

## 1. Purpose and traceability

This section maps technical requirements to the PRD requirement IDs and to the applicable
rules in `master_rules.md`.

| TRD section | PRD requirement IDs | Master rules |
|---|---|---|
| 2. Technology stack | §7 dependencies | 1, 17, 18 |
| 3. Repository & environment | FR-U3, §6 | 1, 13, 17, 18 |
| 4. Dataset requirements & audit | FR-D2, §5 | 4, 15, 16 |
| 5. YOLO11 training pipeline | FR-D1, FR-D2, §5 | 4, 5, 16 |
| 6. Evaluation & acceptance | §3.3, §5 | 14, 15 |
| 7. OpenCV & inference | FR-C1–FR-C4, FR-D3 | 6 |
| 8. Severity & hazard aggregation | FR-K1, FR-K2 | 5, 7 |
| 9. Deterministic risk engine | FR-K1–FR-K4, FR-X1–FR-X3 | 7, 9, 11 |
| 10. Routing & imagery interfaces | FR-R1–FR-R4, FR-I1–FR-I3 | 8, 9, 10 |
| 11. Backend API contracts | FR-R3, FR-D3, FR-K3, FR-L3 | 7, 12, 20 |
| 12. Database design | FR-F1, §4.8 | 13, 18 |
| 13. LLM integration | FR-L1–FR-L3 | 7, 12 |
| 14. Frontend requirements | FR-U1–FR-U3 | 9, 20 |
| 15. Security & error handling | §6 | 13, 19 |
| 16. Testing & integration | §3.3 | 14, 20 |
| 17. Performance & hardware | §7 | 16 |
| 18. Open decisions & order | §8 | 3, 19 |

---

## 2. Proposed technology stack

All items are **[PROPOSED]**. None are installed or operational. No installation will
occur without explicit per-phase approval (Rule 19).

| Layer | Proposed technology | Notes |
|---|---|---|
| Language / runtime | **Python 3.12** in a workspace-local `.venv` | Python 3.14 is the PATH default [VERIFIED] but PyTorch/Ultralytics support is unproven; 3.12 is the safer target. |
| Hazard detection | **Ultralytics YOLO11** | Required by Rule 4. |
| Deep-learning backend | **CUDA-enabled PyTorch** *(if compatible with the actual GPU and driver)* | Audit found a **CPU-only** torch build [VERIFIED]; CUDA must be verified after install. |
| Image processing | **OpenCV** | Image validation, preprocessing, detection visualisation. |
| Backend | **FastAPI** | API layer for routing, analysis, comparison, explanations. |
| Frontend | **React** | Presentation of routes, evidence, limitations. |
| Persistence | **MySQL** | Persistent application data. |
| Local LLM | **Ollama** | Local inference for grounded explanations. |
| Routing provider | **To be selected** | Choice deferred until alternatives, costs and terms are evaluated (§10, §18). |

**Rationale:** the stack is a conventional, well-supported Python + web combination that
maps cleanly onto the audited hardware (RTX 5050 Laptop GPU, 8 GB VRAM, 16 GB RAM). It
keeps the LLM local (Ollama) so no external inference cost or data exposure is required by
default, and keeps the routing provider pluggable behind an interface so provider terms can
be reviewed before commitment.

**Explicitly not claimed:** nothing in this table is installed. `torch`, `ultralytics`,
`cv2`, `numpy` and `yaml` were absent from the PATH-default interpreter; a separate system
Python 3.12 held `torch 2.14.0+cpu`, `ultralytics 8.4.163`, `cv2 5.0.0`, `numpy 2.5.3`
[VERIFIED], but that environment is **outside** the workspace and **CPU-only**.

---

## 3. Repository and environment requirements

### 3.1 Intended directory structure [PROPOSED]

All paths are workspace-relative and must remain inside `D:\New folder (3)` (Rule 1).

```
D:\New folder (3)\
├─ master_rules.md
├─ .gitignore
├─ .env.example                 # template only; no real secrets
├─ README.md
├─ requirements.txt
├─ docs\
│  ├─ PRD.md
│  ├─ TRD.md
│  ├─ ARCHITECTURE.md
│  └─ TRAINING_RULES.md
├─ config\
│  ├─ settings.example.yaml
│  ├─ hazard_severity.yaml
│  └─ risk_engine.yaml
├─ data\
│  ├─ dataset.yaml
│  ├─ images\{train,val,test}\
│  └─ labels\{train,val,test}\
├─ models\
│  ├─ pretrained\
│  └─ training\saferoute-yolo11-v1\
├─ src\
│  ├─ imagery\
│  ├─ preprocessing\
│  ├─ detection\
│  ├─ risk\
│  ├─ routing\
│  ├─ facilities\
│  ├─ llm\
│  └─ api\
├─ frontend\
├─ tests\
│  ├─ unit\
│  ├─ integration\
│  └─ e2e\
├─ logs\
└─ .venv\                      # workspace-local virtual environment
```

### 3.2 Dependency management [PROPOSED]

- A single workspace-local `.venv` created with `py -3.12 -m venv .venv`.
- Pinned dependencies in `requirements.txt` (and `requirements-dev.txt` for tooling).
- No global installs (Rule 1, Rule 18). A lock file (e.g. `pip freeze`) recorded for
  reproducibility.

### 3.3 Configuration and environment variables [PROPOSED]

- Secrets (routing API keys, credentials, database passwords) live **only** in a local
  `.env` that is **not committed** (Rule 13). A committed `.env.example` documents the
  required variable names with placeholder values.
- Non-secret, tunable parameters (thresholds, model version, λ, split ratios) live in
  `config\*.yaml` so behaviour is auditable (Rule 17).
- `.gitignore` must exclude `.env`, `.venv/`, `data/`, `models/`, `logs/`, cache
  directories and large binaries without deleting existing rules (Rule 18).

### 3.4 Logging [PROPOSED]

- Structured logs to `logs\` inside the workspace, with timestamps, component, and no
  secrets or personal data (Rule 13).
- Analysis runs record model version, configuration hash, provider, and coverage so
  results are reproducible and auditable (Rule 17).

### 3.5 Reproducible commands [PROPOSED]

Documented, copy-pasteable commands for: environment creation, dependency install,
dataset audit, training, evaluation, inference, scoring, API startup, frontend startup and
tests. Each phase records the **actual** commands run and their real output (Rule 14).

---

## 4. Dataset requirements and audit

**No dataset exists in the workspace [VERIFIED].** This section defines requirements only;
it does not create or assume a dataset (Rule 19).

### 4.1 Formats

- **Images:** common decodable formats (e.g. `.jpg`, `.png`) readable by OpenCV.
- **Annotations:** YOLO detection format — one `.txt` per image, lines of
  `class_id cx cy w h` normalised to `[0,1]`. Format must be **confirmed against the actual
  dataset** before training; if the dataset uses another format (COCO/VOC), conversion is
  a separate, approved step.

### 4.2 Proposed class IDs

Proposed convention (must be checked against the actual annotation configuration, Rule 15):

| ID | Class |
|---|---|
| 0 | pothole |
| 1 | crack |
| 2 | damaged_patch |
| 3 | waterlogging |
| 4 | uneven_surface |
| 5 | speed_bump |
| 6 | other |

**These IDs are a proposal only.** `data\dataset.yaml` must reflect the class order agreed
with the dataset. Discrepancies must be reported, not silently relabelled (Rule 15).

### 4.3 Required audit checks (before training)

1. **Licence & provenance** — document source, licence, permitted use (Rule 15).
2. **Image–label pairing** — every image has a matching label and vice versa; count
   unpaired items.
3. **Class distribution** — per-class instance counts and image counts; flag imbalance.
4. **Corrupt / unreadable / empty images** — decode check; count failures.
5. **Empty labels** — count images with no objects; do **not** assume an empty label is a
   true negative (Rule 15).
6. **Malformed annotations** — out-of-range or non-numeric values.
7. **Duplicate / near-duplicate detection** — perceptual hashing or embedding similarity.
8. **Split integrity** — verify train/val/test separation; detect the same or near-identical
   images appearing across splits (leakage).
9. **Path safety** — `dataset.yaml` and all configs must reference **workspace-relative**
   paths only; reject any external or absolute-outside paths (Rule 1).

Audit tooling must be read-only against the dataset; corrections require explicit approval
(Rule 15, Rule 19).

---

## 5. YOLO11 training pipeline

**No training will start until dataset integrity (§4) and CUDA capability (Rule 4, 16) are
verified and a dedicated phase is approved (Rule 19).**

### 5.1 Variant strategy [PROPOSED]

- **Baseline first: YOLO11n.** Start smallest/cheapest unless the hardware and dataset
  audit justify another variant. A small model gives a fast, honest baseline.
- **YOLO11m later experiment** — not a mandatory first run. Only after the baseline
  pipeline is proven and hardware headroom is confirmed.

### 5.2 Transfer learning

- Initialise from an appropriate pretrained checkpoint **subject to its availability and
  licence**. Record the exact checkpoint, source and licence (Rule 15, 17).

### 5.3 Configuration

- `data\dataset.yaml` with workspace-relative `path`, `train`, `val`, `test` and `names`.
- **Train/validation/test isolation:** validation drives model selection; the **test set
  stays isolated** until final evaluation.
- Configurable (not guaranteed-optimal) initial parameters:
  - `imgsz`: 640 *(default candidate)*
  - `batch`: small (e.g. 4–16 depending on VRAM)
  - `epochs`: configurable (e.g. 50–100 initial ceiling)
  - `workers`: configurable for Windows/disk characteristics.

### 5.4 GPU, precision, checkpoints, reproducibility

- Verify GPU/VRAM and CUDA-compatible PyTorch before selecting settings (Rule 16).
- Mixed precision (AMP) where supported.
- Save checkpoints and last/best weights inside the workspace model directory.
- Record random seeds, library versions, dataset revision and configuration to make runs
  reproducible (Rule 17).

### 5.5 Early stopping and recovery

- Use early stopping (patience configurable) with validation loss/mAP as the monitored
  signal.
- Support safe resume from the last checkpoint after interruption, without corrupting
  prior runs or logs.

### 5.6 Model version naming

- Canonical version string: **`saferoute-yolo11-v1`** (as used for the training output
  directory `models\training\saferoute-yolo11-v1\`). Model-size details (e.g. `n`/`s`/`m`)
  are recorded **separately** as metadata, so the version label is stable across size
  experiments.

---

## 6. Evaluation and model acceptance

Evaluation is performed only when an actual model and dataset exist. No metric in this
section may be reported until **actually measured** (Rule 14). The **test set stays
isolated** from model selection.

### 6.1 Global metrics
- Precision, recall, **F1**, and **mAP@0.5**.
- **mAP@0.5:0.95**.

### 6.2 Per-class and error analysis
- Per-class precision/recall/mAP and a confusion matrix where supported.
- Analysis of **false positives**, **false negatives** and **class imbalance**.

### 6.3 Qualitative checks
- Inference on held-out images with **human review** of a sample of detections.

### 6.4 Records
- Reproducible training and evaluation records: command, config, seed, versions, dataset
  revision, and the resulting metrics as **measured**, not estimated.

### 6.5 Acceptance
- Model selection uses validation metrics only. Training completion does **not** imply
  production readiness, and no accuracy guarantee may be asserted without measured
  evidence.

---

## 7. OpenCV and inference

### 7.1 Shared, versioned preprocessing [PROPOSED]

- A **single versioned** preprocessing pipeline shared by training and inference where
  applicable (Rule 6). Any divergence is documented and justified.
- **Readable-image checks:** verify decode success, non-null, non-empty, expected channels.
- **Resize / letterbox:** use Ultralytics-consistent letterboxing for inference to avoid
  aspect-ratio distortion; avoid duplicating preprocessing Ultralytics already performs.
- **Colour handling:** consistent colour space (BGR for OpenCV I/O; convert only when a
  consumer requires another space).
- **Optional CLAHE:** applied **only if evaluated** to help or not hurt measured metrics —
  never enabled by default without justification.
- Preserve original images; write annotated outputs to safe workspace paths (Rule 1).

### 7.2 Detection visualisation

- Draw bounding boxes, class labels and confidences onto copies of images; save to a
  designated output/artefact path. Never overwrite source images.

### 7.3 Structured inference outputs [PROPOSED]

Per detection record: model version, image ID, route ID, segment ID, hazard class,
confidence, bounding box (xyxy + normalised), inference status, and error information.
Handle: missing checkpoint, invalid image, empty detections, and inference errors.

### 7.4 Explicit limitation

A single monocular image **cannot** reliably reveal exact pothole depth or real-world
dimensions without suitable calibration and data. The system must **not** claim metric
depth/area from uncalibrated single images.

---

## 8. Severity and hazard aggregation

### 8.1 Detection → hazard record contract [PROPOSED]

```json
{
  "model_version": "saferoute-yolo11-v1",
  "image_id": "img-...",
  "route_id": "route-...",
  "segment_id": "seg-...",
  "hazard_class": "pothole",
  "confidence": 0.0,
  "bbox_xyxy": [0, 0, 0, 0],
  "bbox_norm": [0.0, 0.0, 0.0, 0.0],
  "severity": 0.0,
  "status": "assessed",
  "error": null
}
```

### 8.2 Severity policy

- Severity is assigned by a **documented, testable policy** (e.g. a configurable
  class → base-severity table in `config\hazard_severity.yaml`, optionally modulated by
  confidence and/or normalised bbox area within documented bounds).
- Severity must **not** be decided by the LLM or by arbitrary judgement (Rule 7, 12).
- Every severity value must be explainable from configuration + detection attributes.

### 8.3 Confidence thresholds & duplicates

- A **configurable confidence threshold** filters detections; the value is validated, not
  hard-coded arbitrarily.
- Duplicate/overlapping detections of the same object are handled by a documented rule
  (e.g. IoU-based NMS beyond the model's own NMS) as a **configurable, validated**
  parameter.

---

## 9. Deterministic risk engine

The risk engine is the **only** component that computes safety scores; it is independent of
the LLM (Rule 7). Facility information stays **separate** from the hazard score (Rule 11).

### 9.1 Candidate score

```
S_i = 100 × exp(-λ × H_i)
```

- `S_i` — hazard-risk score for segment/route unit `i` (higher = safer, since larger `H_i`
  reduces `S_i`).
- `H_i` — hazard aggregation for unit `i` *(function **NOT YET DEFINED**; requires
  documented configuration and validation)*.
- `λ` — scaling parameter *(**NOT YET TUNED**; requires documented configuration and
  validation)*.

`H_i` and `λ` are **open items**. They must be specified, justified and validated before
scores are considered meaningful. The formula is a candidate, not a validated calibration.

### 9.2 Required inputs to `H_i` [PROPOSED]

- Verified detections with confidence and severity (§8).
- Segment length / extent and the covered fraction of that segment.
- Image coverage per segment.
- Acquisition status per segment (assessed / partial / failed / unassessed).

### 9.3 Coverage and unknown handling (Rule 9)

- **Missing imagery remains `unknown`/`unassessed`. It must NOT automatically reduce risk.**
  Absence of evidence is not evidence of safety.
- Scores are reported **with** their coverage; insufficient coverage is disclosed and may
  suppress an overall "safe" verdict rather than inflate safety.

### 9.4 De-duplication

- Avoid double-counting the same physical hazard across adjacent segments where identity
  can be established (e.g. overlapping coordinates/imagery or stable hazard identity).

### 9.5 Determinism & separation

- Same inputs → same outputs; implemented as a pure, unit-testable function.
- No dependence on the LLM and no inclusion of facility counts.

---

## 10. Routing and imagery interfaces

### 10.1 Provider-independent interfaces [PROPOSED]

Define abstract interfaces so the provider can be swapped without touching higher layers:

- `get_routes(origin, destination, options) -> Route[]`
- `get_route_geometry(route_id) -> Geometry`
- `get_segment_metadata(route_id) -> Segment[]`
- `get_imagery(segment_id, permitted_source) -> ImageRef[] | Unavailable`

### 10.2 Behaviour for edge cases

| Situation | Required behaviour |
|---|---|
| Provider returns fewer than four routes | Show **exactly** the routes returned (Rule 10). |
| Imagery unavailable for a segment | Mark segment **unassessed**; disclose (Rule 9). |
| Coordinates cannot be matched to segments | Mark **unmatched/unassessed**; disclose. |
| Request fails / times out | Retry with backoff within limits; surface error; mark **failed**. |
| Data stale | Flag **staleness**; do not present stale data as current evidence (Rule 9). |

### 10.3 Provider selection [UNKNOWN]

- The routing provider is **unresolved**. Selection depends on evaluated alternatives,
  costs and terms.
- **Do not assume Google Maps permits automated imagery extraction.** The provider record
  stays "unresolved" until access and usage terms are reviewed and approved. No endpoint,
  permission or dataset may be invented.

---

## 11. Backend API contracts

**[PROPOSED]** endpoints and schemas. These do **not** exist yet and no provider responses
are invented.

### 11.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/routes` | Resolve destination and return available routes. |
| POST | `/api/analyze` | Start safety analysis for a route set. |
| GET | `/api/analyze/{analysis_id}` | Analysis status + results. |
| GET | `/api/analysis/{analysis_id}/hazards` | Hazard detections. |
| GET | `/api/analysis/{analysis_id}/comparison` | Route comparison. |
| GET | `/api/analysis/{analysis_id}/explanation` | Grounded explanation. |
| GET | `/api/health` | Service health. |

### 11.2 Example request / response

**POST `/api/routes`**

```json
{ "origin": "optional", "destination": "required" }
```
```json
{
  "status": "ok",
  "provider": "<selected-or-unresolved>",
  "routes": [
    { "route_id": "r1", "summary": "…", "distance_m": 0, "duration_s": 0, "geometry_ref": "…" }
  ],
  "limitations": ["fewer_than_four_routes_returned"]
}
```

**Analysis status values:** `assessed`, `partially_assessed`, `unassessed`, `failed`.

### 11.3 Error schema [PROPOSED]

```json
{ "status": "failed", "error": { "code": "…", "message": "…", "detail": "…" } }
```

`status` values distinguish assessed / partially assessed / unassessed / failed so the
frontend can disclose coverage honestly (Rule 9, 20).

---

## 12. Database design

**[PROPOSED]** entities and relationships. The database is **not** created in this phase.
Store no more sensitive information than necessary; prefer no personal data (Rule 13).

```
users (id, created_at, prefs_json)
  └─< searches (id, user_id, origin, destination, created_at)
        └─< routes (id, search_id, provider, summary, distance_m, duration_s)
              └─< route_segments (id, route_id, seq, length_m, geometry_ref)
                    └─< imagery_refs (id, segment_id, source, captured_at, licence, path/url, status)
                    └─< hazard_detections (id, segment_id, image_id, model_version_id,
                                           hazard_class, confidence, bbox_json, severity, status)
model_versions (id, name, size, checkpoint_path, trained_at, metrics_json)
scores (id, route_id, model_version_id, config_hash, S, H, coverage, status, computed_at)
analysis_history (id, search_id, created_at, result_json, status)
```

Key relationships: a **search** has many **routes**; a **route** has many **segments**; a
**segment** has many **imagery_refs** and **hazard_detections**; **scores** reference a
route, a model version and a configuration hash for reproducibility.

---

## 13. LLM integration

### 13.1 Boundary

- Backend performs **all** structured calculations (detections, severity, risk scores,
  coverage). The LLM only **explains** verified data and may parse user preferences
  (Rule 7, 12).

### 13.2 Inputs to the LLM [PROPOSED]

- Verified route data (routes actually returned).
- Evidence coverage per route/segment.
- Scoring factors (detections, severities, coverage, computed scores).
- Explicit limitations/unknowns.

### 13.3 Output constraints

- The LLM must **not** introduce new facts (routes, hazards, facilities, measurements) or
  modify the ranking or scores (Rule 12).
- Responses are validated against a schema and checked for references to known entities;
  unknown entity references are rejected.

### 13.4 Fallback

- If **Ollama is unavailable**, return a template-based explanation generated **only** from
  verified backend data (Rule 12), so the product degrades gracefully.

---

## 14. Frontend requirements

- **Destination input** with validation and error states.
- **Route alternatives** — only those actually returned (Rule 10).
- **Route safety score** — displayed as a computed value with its basis.
- **Coverage indicators** — per-route/segment assessed / partial / unassessed.
- **Hazard evidence** — classes, confidences and (optionally) annotated imagery.
- **Facility information presented separately** from the hazard score (Rule 11).
- **Explanations** — grounded, clearly marked as generated from verified data.
- **Errors and loading states** — explicit, non-misleading.
- The UI must **prominently disclose** missing coverage and unassessed segments and clearly
  distinguish working vs. sample/simulated vs. unvalidated features (Rule 9, 20).

---

## 15. Security and error handling

- **Input validation** on all endpoints (types, ranges, string bounds).
- **File upload restrictions** (where applicable): allowed types/sizes, safe storage inside
  the workspace, no path traversal.
- **API timeouts** and bounded retries with backoff for routing/imagery/LLM calls.
- **Rate limits** where applicable (per-client and per-provider).
- **Secret handling:** `.env` only, never committed; `.env.example` documents names
  (Rule 13).
- **Safe logging:** no secrets or personal data in logs.
- **Dependency management:** pinned versions; minimal footprint (Rule 18).
- **Recovery behaviour:** failed/stale analyses are recoverable and reported honestly.

---

## 16. Testing and integration

**[PROPOSED]** test layers, to be executed only when the corresponding components exist.
Actual results must be recorded; nothing may be claimed as passing unless executed
(Rule 14).

- **Unit:** preprocessing, severity mapping, risk engine determinism, provider adapters.
- **Integration:** routing → imagery → preprocessing → detection → scoring pipeline.
- **Model:** dataset audit, training smoke test, evaluation metrics.
- **API:** endpoint contracts, status values, error schemas.
- **UI:** rendering of routes, scores, coverage and errors.
- **End-to-end:** destination → routes → analysis → comparison → explanation.

**Negative tests (required):**
- Missing imagery → `unassessed` (not "safe").
- Invalid annotations → audit failure reported.
- Empty detections → handled distinctly from "no hazards exist".
- LLM unavailable → fallback explanation returned.
- Routing failure / timeout → surfaced error, no fabricated routes.

---

## 17. Performance and hardware constraints

**Audited constraints [VERIFIED]:**

- GPU: **NVIDIA GeForce RTX 5050 Laptop GPU, 8 GB VRAM** (~1.5 GB already in use at audit).
- Driver 616.64 / CUDA UMD 13.4; `nvcc` not on PATH (a toolkit is not required for torch
  wheels).
- System RAM: **16 GB** (only ~1.8 GB free at audit time).
- Disk: D: ~83.5 GB free.
- The only installed PyTorch was **CPU-only** (`torch 2.14.0+cpu`, `torch.cuda.is_available()
  == False`).

**Requirements:**

- **Fresh verification is mandatory before training:** confirm CUDA-enabled PyTorch,
  `torch.cuda.is_available()`, GPU name and free VRAM, and sufficient free RAM/disk.
- Choose batch size / `imgsz` / AMP based on measured VRAM headroom, not assumptions.
- Recommend closing memory-heavy applications (Docker Desktop, IDEs, browsers) before
  training to reduce OOM risk.

---

## 18. Open decisions and implementation order

### 18.1 Open decisions [UNKNOWN]

| # | Decision | Blocks |
|---|---|---|
| 1 | Dataset source, licence and provenance | Training, evaluation |
| 2 | Confirmed annotation format and class IDs | Training, dataset.yaml |
| 3 | Permitted imagery source (terms reviewed) | Assessment pipeline |
| 4 | Routing provider selection (cost/terms) | Core route flow |
| 5 | Credentials/secret management approach | Routing, facilities, DB |
| 6 | Model size (n/s/m) and training schedule | Training |
| 7 | LLM model choice within Ollama | Explanation layer |
| 8 | `H_i` function and `λ` value | Risk scoring validity |
| 9 | Facility provider + confirmation facilities stay separate | Facility display |
| 10 | Deadline-time scope (smallest honest demo) | Delivery |

### 18.2 Dependency-aware implementation order [PROPOSED]

Prioritise a **small, honest demonstration** before advanced features:

1. **Environment** — workspace `.venv` (Python 3.12), pinned deps, CUDA-enabled PyTorch,
   fresh GPU/CUDA verification (§17).
2. **Dataset acquisition + audit** — licence, format, pairing, splits, leakage (§4).
3. **Baseline training** — YOLO11n, transfer learning, recorded configuration (§5).
4. **Evaluation** — measured metrics; isolate test set (§6).
5. **OpenCV + inference** — shared preprocessing, structured detections (§7).
6. **Hazard aggregation + risk engine** — documented severity policy and scoring (§8, §9).
7. **Routing + imagery interfaces** — provider behind an interface; edge-case handling
   (§10).
8. **Backend API** — endpoints, statuses, errors (§11).
9. **LLM explanation** — grounded, with fallback (§13).
10. **Frontend** — routes, scores, coverage, facilities (separate), explanations (§14).
11. **Testing & final validation** — including negative tests (§16).

Each step is gated on explicit approval (Rule 3, 19) and must be verified before the next
begins.

---

## Quality rules acknowledgement

This TRD distinguishes **[VERIFIED]** facts from **[PROPOSED]** choices and **[UNKNOWN]**
items; claims nothing is installed, implemented, trained or tested unless verified; defers
to `master_rules.md` on any conflict; adds no files, directories, packages, datasets or
model weights; and does not alter approved PRD requirements.
