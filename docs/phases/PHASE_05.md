# SafeRoute AI — Phase 05: CUDA / GPU & Training-Readiness Verification

> **Phase ID:** PHASE_05
> **Status:** Complete — approved and documented (see [`../reports/PHASE_05_report.md`](../reports/PHASE_05_report.md))
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

- [x] CUDA availability is stated truthfully as `True`/`False` with raw output. *(Verified: `True`, Torch 2.13.0+cu130).*
- [x] GPU name, capability, VRAM and driver are recorded. *(RTX 5050 Laptop GPU, compute capability 12.0, 8,123 MB VRAM, driver 616.64).*
- [x] RAM and disk figures are recorded. *(15.26 GB RAM, ~1.39 GB free; 79.11 GB free disk on drive `D:`).*
- [x] A provisional settings envelope is recorded (clearly marked provisional). *(Candidate `imgsz=640`, `batch=16`, AMP enabled, conservative workers).*
- [x] Gate status for G11 and G12 is stated. *(G11 PASS, G12 PASS).*
- [x] No training occurred. *(Compute-only tensor op and hardware audit performed).*
- [x] Completion report submitted and accepted. *(Filed in `docs/reports/PHASE_05_report.md`).*

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

## 11. Completion report

> The formal completion report has been filed and recorded:
> - Detailed record: [`docs/reports/PHASE_05_report.md`](../reports/PHASE_05_report.md)

```
PHASE_05 — CUDA / GPU Verification Report
=========================================
Date (actual):           2026-10-13
Interpreter:             D:\New folder (3)\.venv\Scripts\python.exe

1. Torch
   - version:              2.13.0+cu130
   - torch.version.cuda:   13.0
   - cuda.is_available():  True
   - build:                CUDA

2. GPU
   - device count:         1
   - name:                 NVIDIA GeForce RTX 5050 Laptop GPU
   - compute capability:   12.0 (sm_120, 20 SMs)
   - total VRAM:           8,123.44 MB (~8.0 GB)
   - free VRAM:            7,070.00 MB (~6.90 GB at rest)

3. Real execution test
   - result:               PASS — 1024x1024 tensor allocated and multiplied on CUDA with successful cleanup

4. nvidia-smi cross-check
   - driver:               616.64
   - CUDA UMD:             13.4
   - free VRAM (smi):      ~6,612 MiB available (1539 MiB used by desktop processes)

5. Ultralytics
   - version:              8.4.163
   - sees CUDA:            yes (Device 0: NVIDIA GeForce RTX 5050 Laptop GPU)

6. Resources
   - RAM total/free:       15.26 GB / 1.39 GB
   - Disk free (D:):       79.11 GB free (84,945,678,336 bytes)

7. Provisional settings envelope (NOT final)
   - imgsz candidate:      640
   - batch candidate:      16 (fallback to 8 if host memory tight)
   - AMP:                  on (FP16)
   - rationale:            8 GB VRAM provides solid headroom for YOLO11s/n at batch=16 with AMP

8. Gate status
   - G11 GPU/CUDA:  PASS
   - G12 resources: PASS

9. Validation results
   V1 PASS (workspace .venv interpreter verified)
   V2 PASS (torch.cuda.is_available() == True)
   V3 PASS (RTX 5050 Laptop GPU identified and recorded)
   V4 PASS (GPU tensor op executed successfully)
   V5 PASS (VRAM recorded from torch and nvidia-smi)
   V6 PASS (System RAM and workspace drive D: recorded)
   V7 PASS (Ultralytics verified seeing CUDA device)
   V8 PASS (No training executed)

10. Limitations / honesty note
    Host physical RAM free space is ~1.4 GB; training workers should be kept low (workers=2-4)
    and non-essential desktop apps closed prior to full training in PHASE_08.

11. Result: COMPLETE
    Next phase authorised? NO (awaiting user approval for PHASE_06)
```
