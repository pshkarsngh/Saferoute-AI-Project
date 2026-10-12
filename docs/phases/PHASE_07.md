# SafeRoute AI — Phase 07: YOLO11 Baseline Training Plan & Config Freeze

> **Phase ID:** PHASE_07
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_06`](./PHASE_06.md) — OpenCV Preprocessing & Image-Quality Pipeline
> **Successor:** [`PHASE_08`](./PHASE_08.md) — YOLO11 Baseline Training Run
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Freeze the **baseline training plan and configuration** before any run: the dataset YAML, the
class mapping, the split manifest, the baseline variant (YOLO11n), the pretrained checkpoint
provenance, the hyperparameter envelope, and the **evaluation plan**. This satisfies gate
**G13 (baseline plan recorded)** (`TRAINING_RULES.md` §2) and TRD §5.

This phase **plans and configures**; it does **not** train and does **not** download a
checkpoint until that download is separately approved.

---

## 2. Scope

### In scope
- Write `data\dataset.yaml` with workspace-relative `path`, `train`, `val`, `test` and `names`
  consistent with the PHASE_03 class mapping.
- Record the class-ID → class-name mapping and the split manifest reference.
- Choose the baseline variant: **YOLO11n** (proposed) with justification.
- Identify the pretrained checkpoint (source, licence, compatibility) — but do **not** download
  it yet.
- Define the hyperparameter envelope from measured PHASE_05 headroom: `imgsz`, `batch`,
  `epochs`, `workers`, `seed`, optimizer, augmentation, AMP, early-stopping patience.
- Define the **evaluation plan**: metrics (precision, recall, F1, mAP@0.5, mAP@0.5:0.95),
  per-class analysis, confusion analysis, FP/FN review, qualitative sample review.
- Define output/checkpoint/log paths inside `models\training\saferoute-yolo11-v1\` and `logs\`.
- Define an explicit re-check of gates G1–G13 before running.

### Out of scope
- Executing training (PHASE_08).
- Downloading pretrained weights without separate approval.
- Selecting final acceptance thresholds beyond the values written here (they may be refined
  only by an approved plan change).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_03 complete | Verified class mapping + split manifest |
| P2 | PHASE_05 complete | CUDA + resources verified |
| P3 | PHASE_06 complete | Preprocessing pipeline exists |
| P4 | User approves the pretrained checkpoint source/licence | Rule 19 |
| P5 | User approves writing config files | Rule 18 |

---

## 4. Detailed procedure

1. **Dataset YAML.** Write `data\dataset.yaml`:
   - `path:` workspace-relative dataset root;
   - `train:` / `val:` / `test:` split directories or list files;
   - `names:` mapped from the **actual** class IDs (include "unsupported"/excluded classes
     honestly if not trained).
   Confirm no path resolves outside the workspace (Rule 1).
2. **Class mapping & split manifest.** Attach/link the PHASE_03 artefacts. State the exact
   class order used.
3. **Variant decision.** Record baseline = **YOLO11n** with rationale (short deadline, limited
   memory — TRAINING_RULES §3). Larger variants are explicitly deferred.
4. **Checkpoint provenance.** Record the pretrained checkpoint name, source, licence, and
   compatibility with the installed Ultralytics/PyTorch. **Do not download** yet — request
   approval.
5. **Hyperparameter envelope (provisional values, justified by PHASE_05 measurements):**
   - `imgsz` candidate (e.g. 640);
   - `batch` based on measured free VRAM;
   - `epochs` ceiling (configurable);
   - `workers` for Windows/disk;
   - `seed` fixed for reproducibility;
   - optimizer, augmentation flags, AMP on/off, early-stopping patience.
   Mark all numeric values **[PROVISIONAL]** and record the measurement they derive from.
6. **Reproducibility record.** Define what will be captured per run: dataset hash, class
   mapping, split manifest, software versions, checkpoint provenance, effective settings,
   command, timestamp, log/output paths (TRAINING_RULES §4).
7. **Output paths.** Specify:
   - checkpoints → `models\training\saferoute-yolo11-v1\`;
   - logs → `logs\`;
   - evaluation artefacts → `logs\` or `artifacts\`.
   All inside the workspace (Rule 1).
8. **Evaluation plan.** Write the metric list, the isolation rule (test untouched), and the
   qualitative review method.
9. **Gate re-check list.** Enumerate G1–G13 with the evidence source for each, to be confirmed
   at the start of PHASE_08.
10. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_07. |
| A2 | User approves the **pretrained checkpoint** (source + licence) before any download. |
| A3 | User approves the written baseline configuration and evaluation plan. |
| A4 | Any hyperparameter change after freeze requires a documented, approved plan update. |
| A5 | Downloading weights and starting training remain separate approvals (PHASE_08). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Dataset YAML valid | `path`/`train`/`val`/`test`/`names` present and workspace-relative. |
| V2 | Class mapping consistent | YAML `names` match the PHASE_03 verified mapping. |
| V3 | Split manifest referenced | Manifest available and consistent with YAML splits. |
| V4 | Test isolation stated | Evaluation plan isolates the test set. |
| V5 | Variant recorded | Baseline variant recorded with rationale. |
| V6 | Checkpoint provenance recorded | Source + licence recorded (download not yet done). |
| V7 | Settings justified | Every numeric value tied to a measured constraint. |
| V8 | Paths inside workspace | All output paths inside `D:\New folder (3)`. |
| V9 | No training/download | Neither occurred in this phase. |

---

## 7. Acceptance criteria

- [ ] `data\dataset.yaml` exists and is internally consistent with the audit.
- [ ] A frozen baseline configuration and evaluation plan are written and approved.
- [ ] Pretrained checkpoint provenance is recorded and approved (download still pending).
- [ ] Reproducibility capture list is defined.
- [ ] All output paths are inside the workspace.
- [ ] No training or download occurred.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. The class mapping cannot be made consistent between the dataset and `dataset.yaml`
   (Rule 15).
2. Any configured path resolves outside the workspace (Rule 1).
3. The pretrained checkpoint's licence is unclear or incompatible (Rule 19).
4. Hardware headroom (PHASE_05) cannot support even the smallest baseline.
5. A gate (G1–G13) lacks evidence and cannot be evidenced before PHASE_08.

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Isolation | §4.1, §4.7, V8 |
| Rule 4 YOLO11 / gating | §4.3, §4.9 |
| Rule 5 Hazard classes | §4.2 |
| Rule 15 Dataset integrity | §4.1–§4.2 |
| Rule 16 Hardware-aware settings | §4.5 |
| Rule 17 Documentation | §4.6 |
| Rule 19 No unauthorized actions | §5, V9 |
| TRD §5 training pipeline | Whole phase |
| TRAINING_RULES §2 G13, §4 | §4.5–§4.7 |

---

## 10. Honesty note

All numeric hyperparameters are **[PROVISIONAL]** and justified only by measured headroom. No
metric is claimed here. The plan is a hypothesis to be tested in PHASE_08 and measured in
PHASE_09.

---

## 11. Completion report template

```
PHASE_07 — Baseline Plan & Config Freeze
========================================
Date (actual):        <YYYY-MM-DD>

1. Dataset YAML
   - path:       <value>
   - train/val/test: <values>
   - names:      <id->name list>

2. Class mapping (from PHASE_03)
   <table>

3. Split manifest
   - reference:  <path>
   - counts:     train/val/test = <n>/<n>/<n>

4. Baseline variant
   - variant:    YOLO11n
   - rationale:  <short deadline / memory>

5. Pretrained checkpoint (not downloaded)
   - name:       <value>
   - source:     <value>
   - licence:    <value>
   - compatible: <yes/unverified>

6. Hyperparameter envelope (PROVISIONAL)
   - imgsz:      <value>
   - batch:      <value>
   - epochs:     <value>
   - workers:    <value>
   - seed:       <value>
   - optimizer:  <value>
   - AMP:        <on/off>
   - patience:   <value>
   - derived from: <PHASE_05 measurements>

7. Reproducibility capture list
   <items>

8. Output paths
   - checkpoints: <path>
   - logs:        <path>
   - artefacts:   <path>

9. Evaluation plan
   - metrics:    precision, recall, F1, mAP@0.5, mAP@0.5:0.95
   - per-class:  <method>
   - qualitative:<method>
   - test isolation: <confirmed>

10. Gate re-check list (G1–G13)
    <item -> evidence source>

11. Validation results
    V1 <pass/fail + evidence> ... V9 <pass/fail + evidence>

12. Limitations / honesty note
    <provisional values; no metrics claimed>

13. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
