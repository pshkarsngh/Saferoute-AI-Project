# Phase 43 — P2 Acquisition/Governance and P3 Annotation/Freeze

**Date:** 2026-11-10
**Status:** `NOT_ASSESSED`
**Scope:** independent evaluation dataset governance and tooling for Phase 42
**Detector evaluation:** **BLOCKED** — genuine `saferoute-yolo11-v2` checkpoint is still missing

This phase built and executed the governance, validation, ingestion, freeze and
preflight tooling for an independent evaluation dataset. It did **not** acquire
external imagery, accept a licence, invent annotations, invent reviewers, or run
detector inference. No detector metric is reported.

---

## 1. Executive result

| Question | Answer |
|---|---|
| Is real independent imagery present? | **No.** `data/independent/` does not exist. |
| Are approved sources available? | **No.** `docs/datasets/sources.yaml` approves **0** sources. |
| Is the reference registry verified? | **No.** It is filename-date **proxy-only**, `verified=false`. |
| Is there a frozen dataset? | **No.** Freeze correctly refused (`dataset_missing`). |
| Does Phase 42 dataset preflight pass? | **No.** `NOT_ASSESSED` (`dataset_missing`). |
| Can detector evaluation run? | **No.** Dataset missing **and** genuine v2 checkpoint missing. |
| Final dataset status | `NOT_ASSESSED` |

The Phase 42 P1 blocked artifact remains `NOT_ASSESSED`; it was not rewritten by
this phase.

---

## 2. What was actually executed

### 2.1 Source and permission audit (P2.1)

Command:

```
.venv\Scripts\python.exe scripts/phase43/audit_sources.py
```

Result written to `reports/phase43_source_audit.json`:

- 4 candidate sources recorded (`mapillary`, `existing_same_source_corpus`,
  `operator_capture`, `zenodo_18528034`).
- **0 approved** for acquisition.
- The existing corpus is `reference_only: true` and can never supply evaluation
  imagery.
- No download, API call, or licence acceptance occurred.

### 2.2 Reference-session registry (P2.1)

Command:

```
.venv\Scripts\python.exe scripts/phase43/build_reference_registry.py
```

Result written to `reports/phase43_reference_registry.json` and
`reports/phase43_training_sessions.csv`:

- 6 proxy sessions, 1,792 retained images grouped by filename-derived
  `capture_date` (2,009 manifest rows minus 217 `kept=false` duplicates).
- `verified = false`, `session_id_quality = filename_date_proxy`.
- Warnings recorded: no camera ids, no route ids, proxy-only dates.
- Status: `NOT_ASSESSED`.

A proxy registry can never make the independence gate pass. This is intentional.

### 2.3 Acquisition validation and ingestion (P2.2)

Implemented in `src/datasets/acquisition.py` and
`scripts/phase43/ingest_acquisition.py`. It refuses to ingest when:

- the source is not explicitly approved;
- the source is reference-only;
- permission status is not `approved`;
- licence id/evidence is missing;
- an image is undocumented;
- two files share the same SHA-256;
- an image is byte-identical or perceptually near-identical (Hamming ≤ 8) to
  the reference corpus;
- a session crosses splits;
- the output already contains imagery and overwrite was not explicitly granted.

No ingestion was run against real imagery because no source is approved.

### 2.4 Dataset freeze (P3.3)

Command:

```
.venv\Scripts\python.exe scripts/phase43/freeze_dataset.py --frozen-by "not-run"
```

Result written to `reports/phase43_freeze.json`:

- Status `NOT_ASSESSED`, `frozen=false`, `written=false`, reason
  `dataset_missing`.
- No `data/independent/dataset.yaml`, manifest, or hash file was created.

When a real dataset exists, `freeze_dataset` writes `dataset.yaml`,
`manifests/independent_manifest.json`, `manifests/dataset_hashes.json`,
`manifests/collection_sessions.csv`, and `README.md`, and refuses to write a
frozen manifest while any validation error remains.

### 2.5 Phase 42 dataset preflight (P3.3)

Command:

```
.venv\Scripts\python.exe scripts/phase43/preflight_dataset.py
```

Result written to `reports/phase43_dataset_preflight.json`:

- Status `NOT_ASSESSED`, `dataset_ready=false`, reason `dataset_missing`.
- `detector_evaluation_blocked_by_model = true` is recorded even for a future
  passing dataset, because dataset readiness does not supply the v2 checkpoint.

---

## 3. Tooling delivered

### 3.1 Package: `src/datasets/`

| Module | Responsibility |
|---|---|
| `common.py` | Paths, hashing, YAML/JSON helpers, constants, `FreezeStatus` |
| `sources.py` | Source/licence registry; approves nothing by default |
| `acquisition.py` | Provenance schema, duplicate/reference checks, safe ingestion |
| `reference.py` | Proxy reference registry builder/loader |
| `splitting.py` | Deterministic session-atomic split assignment + validators |
| `annotation.py` | Two-review + adjudication evidence validation |
| `freeze.py` | Full validation, manifest generation, hash attestation, tamper check |
| `preflight.py` | Read-only Phase 42 dataset readiness check |

### 3.2 Commands: `scripts/phase43/`

| Command | Purpose |
|---|---|
| `audit_sources.py` | Report approved sources and evidence |
| `build_reference_registry.py` | Build proxy reference registry |
| `split_acquisition.py` | Assign whole sessions to train/val/test deterministically |
| `ingest_acquisition.py` | Validate and copy approved staged imagery |
| `freeze_dataset.py` | Validate, write manifests/hashes, or refuse |
| `preflight_dataset.py` | Phase 42 dataset preflight (no inference) |

### 3.3 Documentation: `docs/datasets/`

- `sources.yaml` — source registry, zero approved.
- `ACQUISITION_PLAN_V1.md` — coverage, provenance, session model, approval gates.
- `ANNOTATION_SPEC_V1.md` — class definitions, bbox rules, ambiguity, negatives,
  review/adjudication protocol, locked test split.
- `templates/` — CSV headers for acquisition, review, adjudication, sessions,
  and reference registry.

---

## 4. Key contracts enforced

1. **No fabricated data.** The dataset directory is not created empty, because
   that would falsely suggest the P1 `independent_dataset_missing` blocker had
   been addressed.
2. **Verified negatives are explicit.** An empty label file is accepted only
   with `outcome=verified_negative` and `final_status=accepted`; a missing label
   file is an error, never a negative.
3. **Two independent reviews.** Exactly one `annotator_a` and one `annotator_b`
   per image, with distinct reviewer ids, plus one adjudication row at the frozen
   annotation version.
4. **Session/route atomicity.** Whole sessions and routes stay in one split;
   violations are errors.
5. **Test split is locked.** Only `final_status=accepted` images may remain in
   `images/test/`.
6. **Freeze hashing matches Phase 42.** The per-split hash material replicates
   `collect_dataset` exactly, so preflight can compare hashes directly.
7. **Not a signature.** `dataset_hashes.json` is documented as a content-hash
   attestation, not a cryptographic signature.

---

## 5. Acceptance criteria

### P2 — acquisition and governance

| Criterion | Status | Evidence |
|---|---|---|
| No unapproved downloads or licence acceptance | **Met by construction** | zero approved sources; tooling has no network acquisition |
| No undocumented imagery | **Met by construction** | ingestion rejects undocumented files; no dataset exists |
| No training/reference session overlap | **Not assessable** | no independent sessions; registry is proxy-only |
| Duplicate/near-duplicate checks completed | **Implemented, not executed on independent data** | exact SHA-256 + DCT pHash checks; no data to run on |
| Missing provenance explicitly reported | **Met** | every blank optional field is counted as unresolved |
| Dataset status remains `NOT_ASSESSED` | **Met** | all Phase 43 reports say `NOT_ASSESSED` |

### P3 — annotation, QC and freeze

| Criterion | Status | Evidence |
|---|---|---|
| All evaluation images have valid provenance | **Not met** | no evaluation images |
| Annotations pass schema/geometry validation | **Validator delivered** | `parse_label_file` + freeze geometry checks |
| Two-person review and adjudication recorded | **Validator delivered; no real records** | `annotation.py` |
| Verified negatives distinguished | **Met in validator** | empty file requires `verified_negative` |
| No unresolved session-level leakage | **Checks delivered; no dataset** | `splitting.py`, `preflight.py` |
| Dataset hashes and version recorded | **Freeze supports it; not written** | freeze refused on missing dataset |
| Phase 42 preflight passes dataset checks | **Not met** | `NOT_ASSESSED`, `dataset_missing` |

---

## 6. Tests

Targeted Phase 43 suite:

```
.venv\Scripts\python.exe -m unittest tests.unit.test_phase43_governance
Ran 25 tests
OK
```

Full suite:

```
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
Ran 459 tests in 90.606s
OK
```

Baseline was 434 tests; Phase 43 adds 25 tests. No existing test was modified.

Phase 43 tests cover: source approval gates, proxy-registry honesty, cross-split
date detection, deterministic session-atomic splitting, provenance/licence
refusal, duplicate and undocumented-image rejection, reference exact-match
rejection, ingestion dry-run/copy/overwrite guard, A/B reviewer independence,
missing adjudication, verified-negative enforcement, excluded-image enforcement,
freeze PASS/PROXY-honesty, Phase 42 hash equality, tamper detection, and
preflight `NOT_ASSESSED`/`PASS` behaviour.

---

## 7. Protected state unchanged

- `config/detection.yaml` SHA-256:
  `22371AE8C1DA3CBA77E40EE096337915D16C0CFDDB9E7E2AF9213F4BE1B18344`
- `config/hazard_severity.yaml` SHA-256:
  `D11AA0F73511E4EEF4B49869D2D009F5F06048801A1B03A64ED5CDB407CDF473`
- Risk engine, risk formula, recommendation eligibility, confidence threshold,
  preprocessing, and production config were not changed.
- `reports/phase42_independent_evaluation.json` remains `NOT_ASSESSED`.
- `P0_SMOKE_SUBSTITUTE.json` was not removed, moved, or bypassed.

---

## 8. What is still blocked, and what would unblock it

### Dataset

1. Name a dataset governance owner and approve at least one source in
   `docs/datasets/sources.yaml` with recorded licence evidence.
2. Capture/export at least 12 independent sessions across road types, lighting,
   weather, cameras and regions, including verified negatives.
3. Run `split_acquisition.py`, then `ingest_acquisition.py` (start with
   `--dry-run`).
4. Annotate with two independent reviewers and record adjudication.
5. Replace the proxy reference registry with a **verified** collection-session
   registry (`verified=true`, `session_id_quality=verified_collection_session`).
6. Run `freeze_dataset.py` and `preflight_dataset.py`.

### Detector

The dataset work is independent of the model, but evaluation also requires the
genuine `saferoute-yolo11-v2` checkpoint. The canonical path currently holds the
P0 smoke substitute (`19619F99…60B916D0`), not genuine v2 (`B6354A56…8800BA`).
If genuine v2 cannot be recovered, any newly trained model must receive a new
model/version identity and must never be reported as v2.

Until both the frozen dataset and the genuine checkpoint exist, the correct
status remains `NOT_ASSESSED` and no detector metric may be claimed.

---

## 9. Final status

```
P2 acquisition/governance tooling: DELIVERED
P3 annotation/freeze/preflight tooling: DELIVERED
Real independent dataset: NOT CREATED
Approved imagery sources: 0
Reference registry: PROXY-ONLY (unverified)
Dataset freeze: REFUSED / NOT WRITTEN
Phase 42 dataset preflight: NOT_ASSESSED
Detector evaluation: BLOCKED (dataset missing + genuine v2 missing)
Overall: NOT_ASSESSED
```
