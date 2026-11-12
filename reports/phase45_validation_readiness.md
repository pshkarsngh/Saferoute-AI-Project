# Phase 45 — Independent Detector Validation Readiness

**Overall readiness status:** **`BLOCKED`**
**Detector evaluation status:** **`NOT_ASSESSED`** (not executed)
**Generated (UTC):** 2026-11-11T17:39:39Z
**Git HEAD:** `b3ee84fc2f2de50eb1fdba6d48d8729179ed49f0` (`main`, uncommitted working tree)
**Baseline:** `reports/phase44_p0_completion.md` + `reports/phase44_evidence/`

> **No detector accuracy, safety, or production-readiness claim is made in this
> document.** No evaluation was run, no checkpoint or marker was modified, no data
> was downloaded, no dependency was installed, and nothing was committed or pushed.
> `null`/`NOT_ASSESSED` means "not measured", never "zero" or "safe".

---

## 1. Executive result

| Question | Answer | Evidence |
|---|---|---|
| Is the genuine registered v2 checkpoint present? | **No.** Canonical path holds the P0 smoke substitute. | §2 |
| Does any local file match the registered v2 SHA-256? | **No.** 11 candidates hashed; 0 match. | §2 |
| Is a genuine independent dataset present? | **No.** `data/independent/` is absent. | §3 |
| Is any imagery source approved for acquisition? | **No.** 0 of 4 candidates approved. | §4 |
| Are annotations, A/B reviews and adjudication present? | **No.** Only templates and a frozen spec; no real records. | §5 |
| Is the dataset frozen? | **No.** Freeze refused (`dataset_missing`). | §5 |
| Is the reference-session registry verified? | **No.** Filename-date proxy only, `verified=false`. | §3.4 |
| Does the Phase 42 model preflight pass? | **No.** Refused the smoke substitute, exit code `2`. | §6 |
| Does the Phase 42 dataset preflight pass? | **No.** `NOT_ASSESSED`, `dataset_missing`. | §6 |
| Can detector evaluation run now? | **No.** Both the genuine checkpoint and the independent dataset are missing. | §7 |

**Conclusion:** genuine independent detector validation **cannot proceed** in the
current workspace. This is an artifact/data-availability blocker, not a detector
result. The correct status is `BLOCKED` (evaluation `NOT_ASSESSED`).

---

## 2. Checkpoint identity and verification

### 2.1 What occupies the canonical serving path

| Field | Value |
|---|---|
| Path | `models/training/saferoute-yolo11-v2/weights/best.pt` |
| SHA-256 | `19619F9934D346600717C8D6C395E7E307B6FB8842F738A225B5B02060B916D0` |
| Size | 5,443,482 bytes |
| Marker | `models/training/saferoute-yolo11-v2/P0_SMOKE_SUBSTITUTE.json` (present) |
| Marker SHA-256 | `8B69C24E7B86976B3038BBA4B5BBFB639094EDC852FBAA4DC49EB933AF795D05` |
| Marker status | `NON_PRODUCTION_P0_SMOKE_SUBSTITUTE` |
| Identity | **P0 smoke substitute — NOT genuine v1 or v2** |

The marker itself states: *"This file is a copy of the P0 smoke model, NOT the
original saferoute-yolo11-v2 artifact. The original checkpoint was not recoverable.
Do not use for safety claims or production evaluation."*

### 2.2 Registered genuine hashes (for comparison only)

| Artifact | Expected SHA-256 | Local match |
|---|---|---|
| Genuine `saferoute-yolo11-v2` | `B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA` | **NONE** |
| Genuine `saferoute-yolo11-v1` | `61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65` | **NONE** |

Source of the pins: `reports/phase42_artifact_manifest.json`,
`reports/phase42_independent_evaluation.json`, and the Phase 20/24D/project-audit
provenance records.

### 2.3 Local model-candidate scan (workspace scope)

All local files ≥1 MB with `.pt/.pth/.onnx/.engine` were hashed (excluding
`.git`, `.venv`, `__pycache__`, `node_modules`, `site-packages`). **11 candidates,
0 matches** for the genuine v2 or v1 hash:

| Path | Bytes | SHA-256 (prefix) | Matches v2? |
|---|---|---|---|
| `yolo11n.pt` | 5,613,764 | `0EBBC80D…` | No |
| `weights/yolo26n.pt` | 5,544,453 | `9B09CC8B…` | No |
| `models/training/p0-smoke/weights/best.pt` | 5,443,482 | `19619F99…` | No |
| `models/training/p0-smoke/weights/last.pt` | 5,443,482 | `7BA35DF6…` | No |
| `models/training/saferoute-yolo11-v1/weights/best.pt` | 5,443,482 | `19619F99…` | No |
| `models/training/saferoute-yolo11-v2/weights/best.pt` | 5,443,482 | `19619F99…` | No |
| `models/training/_tmp_v3_candidate/candidate_v3/weights/best.pt` | 21,251,427 | `8574AB43…` | No |
| `…/candidate_v3/weights/epoch0.pt` | 21,248,867 | `1DAB13A0…` | No |
| `…/candidate_v3/weights/epoch10.pt` | 21,250,147 | `E8757625…` | No |
| `…/candidate_v3/weights/epoch20.pt` | 21,251,427 | `8574AB43…` | No |
| `…/candidate_v3/weights/last.pt` | 21,252,451 | `0A68917A…` | No |

**Note on the v3 candidate.** A newly trained candidate exists at
`models/training/_tmp_v3_candidate/candidate_v3/weights/best.pt`
(`config/training_v3_candidate.yaml`, declared identity
`saferoute-yolo11-v3-candidate`). It is **not** genuine v2, has **no independent
evaluation**, and must never be reported as v2. Its presence does not change the
v2 readiness verdict. Any promotion would require a new identity and its own
frozen independent evaluation.

### 2.4 Phase 42 model preflight (executed read-only)

Command:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_independent.py --preflight-only
```

Result:

```
MODEL INTEGRITY ERROR: The configured checkpoint is the non-production P0 smoke
substitute (marker: ...\P0_SMOKE_SUBSTITUTE.json). An independent v2 evaluation
cannot be reported from it. Restore the genuine saferoute-yolo11-v2 checkpoint,
or pass allow_smoke_substitute for an explicitly harness-only run.
EXIT=2
```

The harness correctly **refuses** the smoke substitute. There is no default path
that converts it into v2 evidence.

---

## 3. Dataset inventory and independence status

### 3.1 Corpora present

| Corpus | Images | Labels | Independence | Usable as evaluation evidence? |
|---|---|---|---|---|
| `data/independent/` | — | — | — | **Absent** |
| `data/derived_2class/` | 2,009 | 1,792 `.txt` | **Same-source** CC BY 4.0 dashcam derivative | **No** |
| `data/pothole_crack_manhole/data/` | 2,009 | 4,018 `.txt` across tree | **Same-source** original corpus | **No** (reference only) |
| `data/imagery/mapillary/` | 1,253 | 0 | Unverified, unannotated, no session/provenance manifest | **No** |

`data/independent/` is intentionally absent. Creating it empty would falsely
suggest the Phase 42 `independent_dataset_missing` blocker had been addressed.

### 3.2 Derived split (same-source, proxy only)

`data/splits_v2/split_manifest.csv` — 2,009 rows:

| Split | Kept | Not kept |
|---|---|---|
| train | 1,398 | 4 |
| val | 178 | 0 |
| test | 216 | 1 |
| quarantine | 0 | 212 |

Columns: `stem, capture_date, split, kept, exclude_reason, n_pothole_src,
n_crack_src, n_manhole_dropped, n_zero_area_dropped, sha256_image, keeper_of`.

- `capture_date` is filename-derived; it spans no multiple splits, so the
  **date-atomic proxy passes for this same-source corpus only**.
- There is **no `session_id` column**, so camera/video/route separation cannot be
  proven.
- This corpus was used for training/validation and can never be the independent
  benchmark.

### 3.3 Mapillary candidate cache — inventory changed since Phase 42/43

Phase 42/43 recorded **98** cached Mapillary images. The current workspace
contains **1,253** images, with newest files written `2026-11-11T22:18:58`
(Phase 44 session date). The directory is gitignored (`data/imagery/`).

There is **no acquisition manifest, no approval record, no per-image licence
evidence, no annotations, and no session manifest** for these files. They remain
**unannotated candidate imagery only**. The clean Phase 42 exact/perceptual probe
(98 vs 2,009 images) does **not** transfer to the expanded 1,253-image cache and
is not a leakage clearance. **No independence is claimed.**

### 3.4 Reference-session registry

`reports/phase43_training_sessions.csv` + `reports/phase43_reference_registry.json`:

- 6 sessions, 1,792 images.
- `session_id_quality = filename_date_proxy`, `verified = false`,
  `proxy_only = true`.
- No camera ids, no route ids.
- Status `NOT_ASSESSED`.

A proxy registry can never make the independence gate pass.

### 3.5 Leakage controls

Controls exist in code (`src/datasets/`, `src/evaluation/leakage.py`) but could
not be executed on independent data because none exists:

- exact SHA-256 duplicate check;
- DCT 64-bit perceptual hash, Hamming ≤ 8;
- exact/perceptual comparison against the reference corpus;
- session-level and route-level split atomicity;
- reference-session overlap check;
- explicit unresolved-provenance reporting.

No leakage clearance is claimed.

---

## 4. Source permission status

Registry: `docs/datasets/sources.yaml`. Audit result: **`approved_count = 0`,
`acquisition_allowed = false`**.

| Source | Licence (project label) | Permission status | Approved | Notes |
|---|---|---|---|---|
| `mapillary` | CC-BY-SA-4.0 | `pending_verification` | **No** | Per-image attribution, share-alike obligations and API terms not re-verified; download needs token + operator approval |
| `existing_same_source_corpus` | CC-BY-4.0 | `pending_verification` | **No** | `reference_only=true`; never independent |
| `operator_capture` | OPERATOR-OWNED | `pending_operator_approval` | **No** | Needs written permission, collection plan, privacy review, named owner |
| `zenodo_18528034` | CC-BY-4.0 | `pending_verification` | **No** | Prior-reported only; record/licence/imagery not independently verified |

Lawful-source requirements before any use:

- **Mapillary:** verify per-image CC-BY-SA 4.0 attribution and share-alike,
  accept API terms, use an approved token, record evidence.
- **Operator capture:** written permission, privacy handling for faces/plates,
  storage/retention decision, named session-id owner.
- **Zenodo 18528034:** verify the record, licence and overlap with the existing
  corpus before use.
- **Google Street View:** disabled; its ToS forbids automated downloading,
  caching and model ingestion.

No download, API call, licence acceptance, or installation was performed in
Phase 45.

---

## 5. Annotation and freeze readiness

### 5.1 Annotation

- Specification: `docs/datasets/ANNOTATION_SPEC_V1.md`, frozen at
  `annotation-v1`; classes `0=pothole`, `1=crack`.
- **No annotations have been performed.**
- **No `annotation_review.csv`, no `adjudication.csv`, no
  `acquisition_manifest.csv`** exist outside `docs/datasets/templates/`.
- No reviewer identities exist — and none were fabricated.
- Required protocol: two independent reviewers (`annotator_a`, `annotator_b`)
  with distinct ids, plus one adjudication per image at `annotation-v1`;
  verified negatives must be explicitly adjudicated; the locked test split
  accepts only `final_status=accepted`.

### 5.2 Freeze

Command (validate only, no write):

```powershell
.\.venv\Scripts\python.exe scripts\phase43\freeze_dataset.py `
  --frozen-by "phase45-readiness-check" --no-write
```

Result:

```
dataset root does not exist: ...\data\independent
EXIT=2
```

`reports/phase43_freeze.json` remains:

```json
{"status": "NOT_ASSESSED", "frozen": false, "written": false,
 "reason": "dataset_missing"}
```

No `dataset.yaml`, manifest, or `dataset_hashes.json` was created.

---

## 6. Phase 42 preflight result

Executed read-only; reports written to temp only (repo artifacts untouched):

| Preflight | Command | Result |
|---|---|---|
| Model integrity | `scripts/evaluate_independent.py --preflight-only` | **Refused**, `MODEL INTEGRITY ERROR`, exit `2` |
| Dataset readiness | `scripts/phase43/preflight_dataset.py` | `NOT_ASSESSED`, `dataset_ready=false`, `reason=dataset_missing`, `detector_evaluation_blocked_by_model=true`, exit `2` |
| Freeze validation | `scripts/phase43/freeze_dataset.py --no-write` | `NOT_ASSESSED`, `dataset_missing`, exit `2` |
| Source audit | `scripts/phase43/audit_sources.py` | `approved_count=0`, `acquisition_allowed=false`, exit `0` |

The existing Phase 42 artifacts remain internally consistent with these results:

- `reports/phase42_independent_evaluation.json` → `NOT_ASSESSED`,
  `evaluation_executed=false`, `metrics.overall=null`, `stage_a.ran=false`,
  `stage_b.ran=false`.
- `reports/phase42_leakage_audit.json` → `NOT_ASSESSED`,
  `independence_established=false`, `leakage_clearance_established=false`.
- `reports/phase43_dataset_preflight.json` → `NOT_ASSESSED`, `dataset_missing`.
- `reports/phase43_freeze.json` → `NOT_ASSESSED`, `dataset_missing`.

No `reports/phase42_stage_a/` directory and no detector metrics exist.

---

## 7. Blockers, owners, actions and evidence

### B1 — Genuine registered v2 checkpoint missing

- **Status:** blocking.
- **Owner:** model owner / operator.
- **Action (preferred):** recover the original serving artifact whose SHA-256 is
  `B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA`, place it
  at `models/training/saferoute-yolo11-v2/weights/best.pt`, record provenance,
  and remove the smoke marker **only** as part of restoring the genuine artifact.
- **Action (if unrecoverable):** formally retire v2 and promote a newly trained
  model under a **new** identity (e.g., the v3 candidate) with its own frozen
  independent evaluation. Never label it v2.
- **Evidence:** §2; `P0_SMOKE_SUBSTITUTE.json`;
  `reports/phase42_artifact_manifest.json`;
  `reports/phase42_independent_evaluation.json`.

### B2 — Independent evaluation dataset absent

- **Status:** blocking.
- **Owner:** dataset governance owner (**not yet named**).
- **Action:** approve source(s) with licence evidence; collect/export at least
  12 independent sessions across road types, lighting, weather, cameras and
  regions; include verified negatives; assign session ids; split; ingest;
  annotate with A/B + adjudication; freeze; preflight.
- **Evidence:** `data/independent/` absent; `reports/phase43_freeze.json`;
  `reports/phase43_dataset_preflight.json`.

### B3 — No approved imagery source

- **Status:** blocking.
- **Owner:** governance owner + operator.
- **Action:** verify licence/terms for at least one source and record
  `permission_status: approved`, `approved_for_acquisition: true`, plus evidence
  in `docs/datasets/sources.yaml`.
- **Evidence:** `reports/phase43_source_audit.json` (`approved_count=0`).

### B4 — No annotations, reviewers or adjudication

- **Status:** blocking.
- **Owner:** annotation lead.
- **Action:** recruit real annotators A/B and an adjudicator; produce
  `annotation_review.csv` and `adjudication.csv` at `annotation-v1`.
- **Evidence:** only `docs/datasets/templates/`; no real review/adjudication files.

### B5 — Reference registry is proxy-only

- **Status:** blocking for the independence gate.
- **Owner:** dataset owner.
- **Action:** replace `reports/phase43_training_sessions.csv` with a **verified**
  collection-session registry (`verified=true`,
  `session_id_quality=verified_collection_session`, camera/route ids).
- **Evidence:** `reports/phase43_reference_registry.json`.

### B6 — Expanded Mapillary cache is unmanifested and unannotated

- **Status:** blocking if it is to be used; otherwise exclude.
- **Owner:** dataset owner.
- **Action:** either formalize it as an approved source with per-image licence
  evidence, an acquisition manifest, session ids, and annotations — or exclude it
  from evaluation.
- **Evidence:** §3.3; `data/imagery/` gitignored; no manifest.

### B7 — v3 candidate is unevaluated

- **Status:** does not unblock v2; separate track.
- **Owner:** model owner.
- **Action:** if pursued, freeze an independent dataset and evaluate the v3
  candidate under its own identity; do not substitute it for v2.
- **Evidence:** `config/training_v3_candidate.yaml`;
  `models/training/_tmp_v3_candidate/`.

### Minimum unblock sequence

```
1. Name a dataset governance owner.
2. Approve ≥1 lawful source in docs/datasets/sources.yaml with licence evidence.
3. Collect/export ≥12 independent sessions (1,500–3,000 images) + verified negatives.
4. split_acquisition.py → ingest_acquisition.py --dry-run → ingest_acquisition.py
5. Annotate A/B + adjudicate at annotation-v1.
6. Build a verified reference-session registry.
7. freeze_dataset.py --frozen-by <owner>
8. preflight_dataset.py
9. Restore the genuine v2 checkpoint (hash B6354A56…8800BA) or formally promote a
   new model identity.
10. evaluate_independent.py --preflight-only   (must exit 0)
11. Run the full evaluation command with explicit operator approval.
```

---

## 8. Exact approved next evaluation command and required approval

### 8.1 Safe preflight (no approval needed; read-only)

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_independent.py --preflight-only
```

This must exit `0` before any evaluation. Today it exits `2`.

### 8.2 Full evaluation (approval-gated; do not run until prerequisites exist)

Canonical Phase 42 command:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_independent.py `
  --dataset-yaml data/independent/dataset.yaml `
  --manifest data/independent/manifests/independent_manifest.json `
  --reference-sessions data/independent/manifests/training_sessions.csv `
  --reference-image-dir data/derived_2class/images `
  --output reports/phase45_independent_evaluation.json
```

**Required approval before execution:**

1. Operator approval for any external download, licence acceptance, or new
   imagery collection (none has been given).
2. Approval for annotation labour (A/B review + adjudication).
3. Explicit approval to execute detector inference against the restored genuine
   checkpoint.
4. Approval to write the evaluation output. A new path
   (`reports/phase45_independent_evaluation.json`) is recommended so the blocked
   Phase 42 baseline is preserved; overwriting
   `reports/phase42_independent_evaluation.json` requires separate approval.

**Do not** pass `--allow-smoke-substitute` for a real evaluation. That flag
produces an explicitly harness-only, `NOT_ASSESSED` run and is not v2 evidence.

---

## 9. Baseline integrity (no Phase 44 regression)

All protected and checkpoint artifacts still match
`reports/phase44_evidence/final_hashes.json`:

| Artifact | Status |
|---|---|
| `config/detection.yaml` | MATCH |
| `config/hazard_severity.yaml` | MATCH |
| `config/risk_engine.yaml` | MATCH |
| `src/risk/engine.py` | MATCH |
| `src/risk/aggregate.py` | MATCH |
| serving checkpoint | MATCH (`19619F99…B916D0`) |
| `P0_SMOKE_SUBSTITUTE.json` | MATCH (`8B69C24E…`) |
| `frontend/assets/index-CXsvefbt.js` | MATCH |
| `frontend/index.html` | MATCH |
| `frontend/model-status.js` | MATCH |
| pre-edit bundle backup | MATCH |

No risk formula, severity threshold, recommendation eligibility, production
config, checkpoint, or marker was changed in Phase 45. No Phase 44 work was
redone.

---

## 10. Scope, method and limitations

- **Read-only:** all checks used existing local artifacts. Preflight reports were
  written only to `C:\Users\pushk\AppData\Local\Temp\`; repository reports were
  not modified.
- **No acquisition:** no imagery downloaded, no licence accepted, no dependency
  installed.
- **No inference:** no detector was loaded; no metric was produced.
- **Checkpoint search scope:** workspace-wide scan of model-format files ≥1 MB.
  The broader Phase 42 P1 search of `D:\` and `C:\Users\pushk` is cited as prior
  evidence and was not re-run across the whole disk in Phase 45.
- **Mapillary discrepancy:** the cache grew from 98 to 1,253 images after the
  Phase 42/43 baseline. No approval or acquisition record explains it; it remains
  unannotated and is not independent evidence.
- **Human review:** no human has reviewed the imagery for this phase; none was
  claimed.

---

## 11. Final status

```
Genuine v2 checkpoint:            MISSING (smoke substitute present, refused)
Genuine v1 checkpoint:            MISSING
Independent dataset:              ABSENT
Approved imagery sources:         0 of 4
Annotations / A/B / adjudication: NONE (templates + frozen spec only)
Verified reference registry:      NO (filename-date proxy, verified=false)
Dataset freeze:                   REFUSED / NOT WRITTEN
Phase 42 model preflight:         FAILED / REFUSED (exit 2)
Phase 42 dataset preflight:       NOT_ASSESSED (dataset_missing)
Detector evaluation:              NOT EXECUTED
Protected state:                  UNCHANGED (matches Phase 44 baseline)

OVERALL READINESS:                BLOCKED
DETECTOR EVALUATION:              NOT_ASSESSED
```

**No detector validation or production-readiness claim is supported.** Evaluation
must not begin until the genuine checkpoint and a frozen, independently acquired
and annotated dataset both exist and the read-only preflight exits `0` with
explicit operator approval.
