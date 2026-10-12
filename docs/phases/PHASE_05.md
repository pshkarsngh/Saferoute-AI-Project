# SafeRoute AI — Phase 05: CUDA / GPU & Training-Readiness Verification

> **Phase ID:** PHASE_05
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_04`](./PHASE_04.md) — Workspace Virtual Environment & Dependencies
> **Successor:** [`PHASE_06`](./PHASE_06.md) — OpenCV Preprocessing & Image-Quality Pipeline
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Verify, from **fresh measurements**, that the workspace environment can actually train YOLO11:
CUDA-enabled PyTorch detects the intended GPU, and RAM/VRAM/disk headroom is sufficient
(gates **G11 (GPU/CUDA)** and **G12 (resources)**). This is the decisive training-readiness gate
required by Rule 4 and Rule 16.

If CUDA is **not** available, this phase records the limitation and **stops** before any
alternate plan is chosen (Rule 16, TRAINING_RULES §2 G11).

---

## 2. Scope

### In scope
- Verify `torch.cuda.is_available()` in the `.venv` interpreter.
- Record `torch.cuda.get_device_name()`, device count, capability, and total/free VRAM.
- Run a **small tensor allocation** on the GPU to confirm real execution (no training).
- Record total/free system RAM and free disk on the workspace drive.
- Confirm Ultralytics can import and that it sees the CUDA device.
- Estimate a **provisional** memory budget for the chosen model size (no training).
- Record recommended settings constraints (max `batch`, `imgsz`) — provisional only.

### Out of scope
- Any training run (PHASE_08).
- Downloading pretrained checkpoints (PHASE_07).
- Selecting final hyperparameters (PHASE_07).
- Installing different packages (unless a fix is separately approved).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_04 complete and accepted | `.venv` with packages installed |
| P2 | PHASE_03 complete | Dataset audited |
| P3 | User approves running verification commands | Read-only/compute-only |
| P4 | Memory-heavy applications closed where possible | Reduce OOM risk (TRD §17) |

---

## 4. Detailed procedure

1. **Confirm the interpreter.** Ensure commands run inside
   `D:\New folder (3)\.venv\Scripts\python.exe`.
2. **CUDA availability:**
   ```
   python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
   ```
3. **Device details:**
   ```
   python -c "import torch; print(torch.cuda.get_device_name(0)); print(torch.cuda.get_device_properties(0))"
   ```
   Record name, total memory, compute capability, device count.
4. **Real GPU execution test (no training):** allocate a small tensor on CUDA and perform a
   trivial op; confirm success and record free VRAM before/after via
   `torch.cuda.mem_get_info()`.
5. **GPU/driver cross-check:** run `nvidia-smi`; reconcile reported free VRAM with torch's.
6. **Ultralytics import & device check:** import `ultralytics`; confirm the version and that a
   CUDA device is selectable.
7. **System resources:** record total/free RAM and free/total disk on `D:`.
8. **Provisional settings envelope:** based on measured free VRAM, note a **conservative**
   starting `batch`/`imgsz` range for the baseline (to be finalised in PHASE_07). Label these
   as **provisional** (Rule 16).
9. **Determine gate status** for G11 and G12. If G11 fails (CUDA unavailable), stop and report.
10. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_05. |
| A2 | User approves the verification commands (compute-only, non-destructive). |
| A3 | If CUDA is unavailable, choosing any alternative (e.g. CPU training) requires a **new** explicit approval and a documented plan (Rule 16). |
| A4 | Any package change to fix CUDA requires separate approval (Rule 19). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Correct interpreter | Commands run in the workspace `.venv`. |
| V2 | CUDA available | `torch.cuda.is_available()` is `True` (G11). |
| V3 | GPU identified | Device name and capability recorded and match the intended GPU. |
| V4 | Real execution | A GPU tensor op succeeds. |
| V5 | VRAM recorded | Total/free VRAM recorded from torch and cross-checked with `nvidia-smi`. |
| V6 | RAM/disk recorded | Free RAM and free disk recorded (G12). |
| V7 | Ultralytics ready | `ultralytics` imports and sees the CUDA device. |
| V8 | No training | No training run was started. |

---

## 7. Acceptance criteria

- [ ] CUDA availability is stated truthfully as `True`/`False` with raw output.
- [ ] GPU name, capability, VRAM and driver are recorded.
- [ ] RAM and disk figures are recorded.
- [ ] A provisional settings envelope is recorded (clearly marked provisional).
- [ ] Gate status for G11 and G12 is stated.
- [ ] No training occurred.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report immediately if:
1. `torch.cuda.is_available()` is `False` (G11 fail) — do not silently proceed (Rule 16).
2. Free VRAM is far below what the intended model needs.
3. Free RAM/disk is insufficient for the dataset and checkpoints (G12 fail).
4. The installed torch is CPU-only.
5. GPU execution errors occur and cannot be explained.
6. Fixing the environment would require an unapproved install/upgrade (Rule 19).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 4 YOLO11 readiness gating | §1, §4.9 |
| Rule 16 Hardware awareness | Whole phase |
| Rule 17 Documentation | §4, §11 |
| Rule 19 No unauthorized actions | §5, §8.6 |
| TRD §17 constraints | §4.7–§4.8 |
| TRAINING_RULES §2 G11, G12 | §5, V2, V6 |

---

## 10. Honesty note

A CUDA-capable environment is a **prerequisite**, not a result. This phase asserts only what was
measured. It does not claim the model trains well, nor that metrics exist — those require
PHASE_08–PHASE_09.

---

## 11. Completion report template

```
PHASE_05 — CUDA / GPU Verification Report
=========================================
Date (actual):           <YYYY-MM-DD>
Interpreter:             <path>

1. Torch
   - version:              <value>
   - torch.version.cuda:   <value or None>
   - cuda.is_available():  <True/False>
   - build:                CUDA / CPU-only

2. GPU
   - device count:         <n>
   - name:                 <value>
   - compute capability:   <x.y>
   - total VRAM:           <value>
   - free VRAM:            <value>

3. Real execution test
   - result:               <pass/fail + details>

4. nvidia-smi cross-check
   - driver:               <value>
   - CUDA UMD:             <value>
   - free VRAM (smi):      <value>

5. Ultralytics
   - version:              <value>
   - sees CUDA:            <yes/no>

6. Resources
   - RAM total/free:       <value>
   - Disk free (D:):       <value>

7. Provisional settings envelope (NOT final)
   - imgsz candidate:      <value>
   - batch candidate:      <value>
   - AMP:                  <on/off>
   - rationale:            <measured headroom>

8. Gate status
   - G11 GPU/CUDA:  PASS / FAIL
   - G12 resources: PASS / FAIL

9. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

10. Limitations / honesty note
    <observed constraints>

11. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
