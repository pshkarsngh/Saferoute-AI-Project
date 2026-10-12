# SafeRoute AI — Phase 08: YOLO11 Baseline Training Run

> **Phase ID:** PHASE_08
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_07`](./PHASE_07.md) — YOLO11 Baseline Training Plan & Config Freeze
> **Successor:** [`PHASE_09`](./PHASE_09.md) — Model Evaluation & Checkpoint Acceptance
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Execute **one controlled baseline training run** of YOLO11n on the audited dataset, using the
frozen configuration from PHASE_07, with strict logging, checkpoint storage inside the
workspace, and no test-set exposure. This is the **first and only** action that runs training,
and it requires a dedicated approval (Rule 19).

No metrics are reported in this phase; evaluation happens in PHASE_09.

---

## 2. Scope

### In scope
- A final gate confirmation (G1–G13) immediately before launch.
- Optional approved download of the pretrained checkpoint.
- One baseline training run using `data\dataset.yaml` and the frozen config.
- Logging to `logs\` and checkpoints to `models\training\saferoute-yolo11-v1\`.
- Robust handling of interruption (resume from last checkpoint) and OOM (clean stop, minimal
  documented change) per TRAINING_RULES §5.
- Capture of the full run record (versions, seed, settings, command, timestamp, paths).

### Out of scope
- Evaluation on the test set (PHASE_09).
- Tuning beyond the frozen plan (a plan change needs approval).
- Deleting prior checkpoints/logs (Rule 19).
- Production readiness claims.

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_07 complete & approved | Frozen config + evaluation plan |
| P2 | Gates G1–G13 all pass | Re-confirmed at start of this phase |
| P3 | User **explicitly approves the training run** | Rule 19 |
| P4 | Pretrained checkpoint download approved (if required) | Rule 19 |
| P5 | Free VRAM/RAM/disk confirmed sufficient | PHASE_05 |
| P6 | Memory-heavy applications closed where possible | Reduce OOM risk |

---

## 4. Detailed procedure

1. **Re-confirm all gates G1–G13** with evidence. If any fails, **stop** (Rule 4, Rule 15,
   Rule 16).
2. **Confirm no path resolves outside the workspace.** Dataset, config, checkpoints, logs.
3. **Obtain the pretrained checkpoint** only if approved; record source, licence and hash.
4. **Capture the reproducibility record** (versions, dataset hash, class map, split manifest,
   effective settings, seed, command, timestamp).
5. **Launch the single baseline run** exactly per the frozen config. Example form (final command
   per approved plan):
   ```
   python -m ultralytics ... train data="data\dataset.yaml" model=<approved-checkpoint> epochs=<N> imgsz=<N> batch=<N> seed=<N> project="models\training" name="saferoute-yolo11-v1"
   ```
   Run inside `.venv`; all outputs inside the workspace.
6. **Monitor** for errors, warnings, OOM and divergence. Do not make unrecorded changes.
7. **On OOM:** stop cleanly, preserve logs/checkpoints, apply the **minimal** documented
   mitigation (lower `batch`, smaller `imgsz`, or AMP), record the change and reason, and only
   continue if permitted by the approved plan (TRAINING_RULES §5).
8. **On interruption:** resume from the last checkpoint without corrupting prior runs/logs.
9. **On completion:** confirm best/last checkpoints exist and record their paths and hashes.
   Do **not** evaluate the test set here.
10. **Do not delete** any prior checkpoints or logs.
11. **Write the completion report** (§11) with the actual run record — no metrics invented.

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User explicitly approves starting PHASE_08 (training). |
| A2 | User approves the pretrained checkpoint download (if applicable). |
| A3 | Any deviation from the frozen plan (epochs, batch, imgsz, resume) requires approval and a documented plan update. |
| A4 | Deleting checkpoints/logs requires separate approval (Rule 19). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Gates confirmed | G1–G13 all pass with recorded evidence. |
| V2 | Isolation | No path resolves outside the workspace. |
| V3 | Reproducibility record | Versions/seed/settings/command/timestamp captured. |
| V4 | Checkpoints saved | best/last weights exist at the documented path. |
| V5 | Logs saved | Training logs exist in `logs\`. |
| V6 | Test untouched | No test-set evaluation performed. |
| V7 | No silent changes | Every deviation recorded with reason. |
| V8 | Prior artefacts intact | No prior checkpoint/log deleted. |

---

## 7. Acceptance criteria

- [ ] All gates confirmed immediately before the run.
- [ ] One documented baseline run completed (or stopped cleanly with a recorded reason).
- [ ] Checkpoints and logs exist inside the workspace with recorded hashes.
- [ ] Full run record captured.
- [ ] Test set untouched.
- [ ] No metrics claimed in this phase.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report immediately if:
1. Any gate G1–G13 fails.
2. A path resolves outside the workspace (Rule 1).
3. Unexpected changes appear in the dataset or config (TRAINING_RULES §5).
4. Unresolved OOM or repeated crashes beyond the approved mitigation.
5. Numerical divergence/NaNs or clearly broken training appear.
6. Any step would require an unapproved action (Rule 19).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Isolation | §4.2, V2 |
| Rule 3 One phase at a time | Whole phase |
| Rule 4 YOLO11 / gating | §4.1 |
| Rule 14 Testing honesty | §4.9, §7 |
| Rule 16 Hardware-aware training | §4.5–§4.7 |
| Rule 17 Documentation | §4.4, V3 |
| Rule 18 Minimal changes | §4.7, V8 |
| Rule 19 No unauthorized actions | §5, §8.6 |
| TRAINING_RULES §2, §4, §5 | Whole phase |

---

## 10. Honesty note

A completed run means training **executed**, not that the model is good, balanced or
production-ready. No precision/recall/mAP may be stated until measured in PHASE_09.

---

## 11. Completion report template

```
PHASE_08 — Baseline Training Run Report
=======================================
Date (actual):        <YYYY-MM-DD>
Approval reference:   <user approval of training>

1. Gate confirmation (G1–G13)
   <each: pass + evidence>

2. Reproducibility record
   - dataset hash/manifest: <value>
   - class mapping:         <reference>
   - split manifest:        <reference>
   - python:                <version>
   - torch/cuda:            <versions>
   - ultralytics:           <version>
   - opencv:                <version>
   - os/driver:             <values>
   - model variant:         n
   - pretrained checkpoint: <name + source + licence + hash>

3. Command (exact)
   <verbatim>

4. Effective settings
   - imgsz/batch/epochs/workers/seed/AMP/patience: <values>

5. Run outcome
   - status:        completed / stopped (reason)
   - start/end time:<...>
   - duration:      <...>
   - warnings/errors:<...>

6. Artefacts
   - best checkpoint:  <path + hash>
   - last checkpoint:  <path + hash>
   - logs:             <path>
   - prior artefacts intact: <yes>

7. Deviations from plan
   <none | list with reason + approval>

8. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

9. Limitations / honesty note
   <no metrics claimed; training != readiness>

10. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
