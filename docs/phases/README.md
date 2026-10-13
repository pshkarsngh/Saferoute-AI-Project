# SafeRoute AI — Phase Index

> **Project:** SafeRoute AI — Intelligent Road Safety Navigation System
> **Workspace:** `D:\New folder (3)`
> **Status:** Phases 00–18 delivered (reports in `../reports/`); PHASE_17 uses the deterministic fallback and PHASE_13 OSRM / PHASE_14 Mapillary / PHASE_15 Overpass live paths are implemented but offline-verified
> **Date:** 2026-10-14
> **Governing rules:** [`../../master_rules.md`](../../master_rules.md) (authoritative)
> **Companion documents:** [`../PRD.md`](../PRD.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

This directory is the **single index of delivery phases** for SafeRoute AI. Every phase has
its own Markdown file (`PHASE_00.md` … `PHASE_18.md`) containing its objective, prerequisites,
detailed procedure, approval gates, validation checks, acceptance criteria, stop conditions and
a completion-report template.

**Status:** all 19 phases have completion reports under [`../reports/`](../reports/). A dataset,
GPU-trained YOLO11 baseline, detection/aggregation/risk modules, routing and imagery adapters,
a facilities service, a backend API with persistence, an explanation layer (fallback) and a
frontend now exist in the workspace. Live third-party paths (OSRM, Mapillary, Overpass, Ollama)
are implemented but were verified offline; enabling them requires per-phase approval (Rule 19).

---

## 1. How to use this index

1. Read [`../../master_rules.md`](../../master_rules.md) and the four companion documents before
   any phase.
2. Open the phase file for the next phase in the dependency chain.
3. Obtain **explicit approval** for that phase (Rule 3, Rule 19) before performing its procedure.
4. Execute only the steps the phase authorises. Do not run steps that belong to a later phase.
5. Fill in the **completion report template** using **actual observed results** (Rule 14).
6. Present the completion report and wait for approval before starting the successor phase.

Phases are executed **one at a time** and each must be verified before the next begins
(Rule 3). Skipping, reordering or partially executing a phase without approval violates
`master_rules.md`.

---

## 2. Phase table

| Phase | Title | Primary output | Status |
|---|---|---|---|
| [PHASE_00](./PHASE_00.md) | Documentation Baseline & Phase Governance | Frozen, approved governing document set and phase framework | Complete |
| [PHASE_01](./PHASE_01.md) | Workspace & Environment Audit (read-only) | Read-only environment/hardware audit report | Complete |
| [PHASE_02](./PHASE_02.md) | Dataset Acquisition & Licence Approval Gate | Documented dataset source, licence and provenance | Complete |
| [PHASE_03](./PHASE_03.md) | Dataset Integrity, Class-Mapping & Split Audit | Dataset audit report and verified class/split manifest | Complete |
| [PHASE_04](./PHASE_04.md) | Workspace Virtual Environment & Dependencies | Workspace-local `.venv` with pinned dependencies | Complete |
| [PHASE_05](./PHASE_05.md) | CUDA / GPU & Training-Readiness Verification | Verified GPU/CUDA/resource report | Complete |
| [PHASE_06](./PHASE_06.md) | OpenCV Preprocessing & Image-Quality Pipeline | Single versioned preprocessing/validation module | Complete |
| [PHASE_07](./PHASE_07.md) | YOLO11 Baseline Training Plan & Config Freeze | `dataset.yaml`, frozen baseline config and evaluation plan | Complete |
| [PHASE_08](./PHASE_08.md) | YOLO11 Baseline Training Run | Trained baseline checkpoints + run record | Complete |
| [PHASE_09](./PHASE_09.md) | Model Evaluation & Checkpoint Acceptance | Measured metrics and accept/reject/rollback decision | Complete |
| [PHASE_10](./PHASE_10.md) | Inference & Structured Detection Pipeline | Versioned inference module emitting structured detections | Complete |
| [PHASE_11](./PHASE_11.md) | Hazard Aggregation & Severity Policy | Documented severity policy and aggregation service | Complete |
| [PHASE_12](./PHASE_12.md) | Deterministic Risk Engine | Pure, unit-tested risk scoring function and config | Complete |
| [PHASE_13](./PHASE_13.md) | Routing Provider Selection & Adapter | Approved provider and provider-independent route adapter | Complete |
| [PHASE_14](./PHASE_14.md) | Permitted Imagery Acquisition Adapter | Imagery adapter limited to permitted sources | Complete |
| [PHASE_15](./PHASE_15.md) | Facilities Lookup Service | Facility service kept separate from the hazard score | Complete |
| [PHASE_16](./PHASE_16.md) | Backend API & Persistence | Backend endpoints with status/error schemas and SQLite schema | Complete |
| [PHASE_17](./PHASE_17.md) | Grounded LLM Explanation Layer | Schema-validated, grounded explanations with fallback | Complete (fallback) |
| [PHASE_18](./PHASE_18.md) | Frontend Integration & End-to-End Validation | Frontend comparison UI and full E2E + negative test evidence | Complete |

---

## 3. Dependency chain

```
PHASE_00  Documentation & governance
   └─ PHASE_01  Environment audit (read-only)
        └─ PHASE_02  Dataset acquisition & licence gate
             └─ PHASE_03  Dataset integrity audit
                  └─ PHASE_04  Virtual environment & dependencies
                       └─ PHASE_05  CUDA / GPU verification
                            └─ PHASE_06  OpenCV preprocessing pipeline
                                 └─ PHASE_07  Training plan & config freeze
                                      └─ PHASE_08  Baseline training run
                                           └─ PHASE_09  Evaluation & acceptance
                                                └─ PHASE_10  Inference pipeline
                                                     └─ PHASE_11  Hazard aggregation & severity
                                                          └─ PHASE_12  Deterministic risk engine
                                                               ├─ PHASE_13  Routing adapter
                                                               ├─ PHASE_14  Imagery adapter
                                                               └─ PHASE_15  Facilities service
                                                                    └─ PHASE_16  Backend API & persistence
                                                                         └─ PHASE_17  LLM explanation layer
                                                                              └─ PHASE_18  Frontend & E2E validation
```

**Hard blockers:**
- `PHASE_08` (training) cannot run unless `PHASE_02`–`PHASE_05` and all TRAINING_RULES §2 gates
  (G1–G13) pass.
- `PHASE_12` onward cannot present meaningful results without a trained, accepted model
  (`PHASE_08`–`PHASE_09`) and permitted imagery (`PHASE_14`).
- `PHASE_13` and `PHASE_14` depend on provider/imagery decisions that are currently
  **[UNKNOWN]** (TRD §18.1, ARCHITECTURE §13).

---

## 4. Status legend

| Status | Meaning |
|---|---|
| **Not started** | No procedure step has been executed; no output exists. |
| **In progress** | Approved and partially executed; results not yet verified. |
| **Blocked** | Approved but cannot proceed (missing prerequisite, gate failure or unresolved decision). |
| **Awaiting approval** | Procedure complete; completion report submitted; next phase not authorised. |
| **Complete** | Reviewed, validated against acceptance criteria and explicitly approved. |

> All phases now have completion reports; see the reports directory for actual results.

---

## 5. Global approval gate (applies to every phase)

- **No phase may begin without explicit user approval for that specific phase** (Rules 3, 19).
- **No phase may be marked complete** until its validation checks pass and the user accepts the
  completion report.
- The following actions **always** require a dedicated, explicit approval and are never implied
  by approval of another phase (Rule 19):
  - downloading a dataset or pretrained checkpoint;
  - installing or upgrading any package;
  - creating API credentials or paid-service accounts;
  - calling any paid API;
  - modifying or relabelling any dataset file;
  - starting, resuming or re-running training.

---

## 6. Global stop conditions

Stop immediately and report if any of the following occur during **any** phase:

1. A path resolves **outside** `D:\New folder (3)` without explicit user authorisation (Rule 1).
2. A step would require an action from Rule 19 that has not been approved.
3. Existing project files would be modified in a way the phase did not authorise
   (Rules 18, 19).
4. A validation check fails or produces ambiguous results (Rule 14).
5. Any result cannot be reproduced or is suspected of being fabricated (Rule 14, Rule 20).
6. A conflict is found between governing documents (must be raised, never silently overridden).
7. Hardware, dataset or environment conditions differ materially from what the phase assumed.

---

## 7. Cross-phase honesty rules (from `master_rules.md`)

- Report only **actually measured** results; never fabricate metrics, coverage or tests
  (Rule 14).
- Missing/insufficient evidence is **unknown / unassessed**, never proof of a safe road
  (Rule 9).
- The **deterministic risk engine** owns all safety scores; the LLM only explains (Rules 7, 12).
- **Facilities** stay separate from the hazard score (Rule 11).
- Only **permitted** imagery sources may be used; routing APIs do **not** automatically grant
  imagery-reuse permission (Rule 8).
- Clearly separate **working**, **simulated/sample**, and **unvalidated** capabilities
  (Rule 20).

---

## 8. Known open item carried into the phases

**Model-version spelling inconsistency (must be resolved by an approved documentation update,
never an ad-hoc edit):** `docs\PRD.md` §5 uses `safroute-yolo11-v1`, whereas `docs\TRD.md` §5.6
and `docs\ARCHITECTURE.md` §5 use `saferoute-yolo11-v1`. Until reconciled, phases reference
**`saferoute-yolo11-v1`**. See PHASE_00 §7.

---

## 9. Phase file structure (what every phase contains)

Every `PHASE_NN.md` file contains, in order:

1. Objective
2. Scope (in scope / out of scope)
3. Prerequisites
4. Detailed procedure (step-by-step)
5. Approval gates
6. Validation checks
7. Acceptance criteria
8. Stop conditions
9. Traceability to the governing documents
10. Completion report template
