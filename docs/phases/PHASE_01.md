# SafeRoute AI — Phase 01: Workspace & Environment Audit (read-only)

> **Phase ID:** PHASE_01
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_00`](./PHASE_00.md) — Documentation Baseline & Phase Governance
> **Successor:** [`PHASE_02`](./PHASE_02.md) — Dataset Acquisition & Licence Approval Gate
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../PRD.md`](../PRD.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Produce an **accurate, read-only snapshot** of the workspace and host environment so that later
phases choose configurations based on **measured facts**, not assumptions (Rule 16). This
phase records what actually exists: files, Python interpreters, installed packages, GPU, CUDA,
RAM and disk space.

This phase **installs nothing, downloads nothing, and edits no files**. It performs read-only
queries only.

---

## 2. Scope

### In scope
- Inventory the workspace tree under `D:\New folder (3)` (files, sizes, obvious large binaries).
- Detect available Python interpreters and their versions.
- Detect already-installed relevant packages (e.g. `torch`, `ultralytics`, `opencv`/`cv2`,
  `numpy`, `PyYAML`) **in already-present interpreters only** — no installation.
- Record GPU name, VRAM, driver/CUDA UMD, `torch.cuda.is_available()` for any present torch.
- Record system RAM (total/free) and free disk on the workspace drive.
- Note OS version and architecture.
- Cross-check the findings against the audit already recorded in `TRD.md` §17.

### Out of scope
- Creating a virtual environment (§PHASE_04).
- Installing or upgrading any package (Rule 19).
- Downloading datasets or checkpoints (Rules 19; PHASE_02).
- Modifying any project file (Rule 18).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_00 complete and accepted | Documentation baseline frozen |
| P2 | Read access to the workspace and host | No admin rights required |
| P3 | User approves a read-only audit | Rule 3 |

---

## 4. Detailed procedure

1. **Workspace inventory.** List files under `D:\New folder (3)` (recursive), capturing paths
   and sizes. Explicitly flag: dataset archives, image folders, model weights, and any
   directory named `.venv`, `models`, `logs`, `src`, `frontend`, `tests`, `config`.
2. **Confirm isolation.** Verify every discovered project path is inside
   `D:\New folder (3)` (Rule 1). Record anything that resolves outside it.
3. **Python discovery.** Enumerate available interpreters:
   - `py -0p` (Windows launcher) if present;
   - `python --version`, `py -3.12 --version`, `py -3.13 --version` where available.
   Do **not** install any interpreter.
4. **Package inventory (existing environments only).** For each discovered interpreter, record
   versions of `torch`, `ultralytics`, `cv2`, `numpy`, `yaml` **if already installed**. Do not
   install missing packages.
5. **CUDA/torch check (read-only).** If a torch build is present, record:
   - `torch.__version__`, `torch.version.cuda`, `torch.cuda.is_available()`, device name.
   Mark clearly whether the build is CPU-only.
6. **GPU/driver query.** Record `nvidia-smi` output if available: GPU name, driver version,
   CUDA UMD/runtime version, total and free VRAM.
7. **System resources.** Record total/free RAM and free/total disk on the workspace drive.
8. **OS/architecture.** Record OS build, architecture (x64/arm64), and shell used.
9. **Reconcile with `TRD.md` §17.** Note any difference between this fresh, read-only audit and
   the previously recorded audit.
10. **Write the completion report** (§11) using actual observed values only.

**Illustrative read-only commands (subject to the host's availability — run only if approved):**
```
Get-ChildItem 'D:\New folder (3)' -Recurse -File | Measure-Object -Property Length -Sum
py -0p
python --version
python -c "import torch, sys; print(sys.version); print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
nvidia-smi
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
Get-PSDrive D
```

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_01. |
| A2 | User approves the specific read-only commands before they are run. |
| A3 | Any command that would install, download or modify state is **out of scope** and requires separate approval (Rule 19). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Isolation | All reported project paths are inside `D:\New folder (3)`. |
| V2 | Inventory complete | File/space inventory captured with counts and sizes. |
| V3 | Interpreter list | All available Python interpreters recorded with versions. |
| V4 | Package list | Versions recorded for any present relevant packages; "absent" recorded explicitly. |
| V5 | Torch/CUDA status | CPU-only vs CUDA-capable recorded from the interpreter actually inspected. |
| V6 | GPU/driver captured | GPU name, driver and VRAM recorded, or "nvidia-smi unavailable" recorded. |
| V7 | Resources captured | RAM and disk figures recorded. |
| V8 | No state change | No install, download, or file modification occurred. |

---

## 7. Acceptance criteria

- [ ] Command outputs recorded verbatim (or clearly summarised with the raw output saved).
- [ ] Present vs absent dependencies explicitly stated.
- [ ] CUDA availability for the inspected torch stated truthfully.
- [ ] Any divergence from `TRD.md` §17 noted.
- [ ] No file was created, modified or deleted.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. A discovered path resolves outside the workspace (Rule 1).
2. A needed command would install/download/modify state (Rule 19).
3. The audit contradicts `TRD.md` §17 in a way that changes later assumptions (raise for
   reconciliation).
4. GPU or driver information cannot be obtained and is required by a later gate.

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Isolation | §4.2, V1 |
| Rule 16 Hardware awareness | §4.6–§4.8 |
| Rule 17 Documentation | Whole phase |
| Rule 18 Minimal changes | §2 out-of-scope, V8 |
| Rule 19 No unauthorized actions | §5, §8 |
| TRD §17 constraints | §4.9 |

---

## 10. Honesty note

This phase measures the **current** environment only. It does not create a training-ready
environment, and it does not assume the presence of CUDA, a dataset, or any dependency.

---

## 11. Completion report template

```
PHASE_01 — Completion Report
============================
Date (actual):              <YYYY-MM-DD>
Commands run (exact):       <list>
Raw output saved to:        <path or "not saved">

1. Workspace inventory
   - Total files:            <N>
   - Total size:             <size>
   - Notable dirs present:   <list or "none">
   - Paths outside workspace:<list or "none">

2. Python interpreters
   - <interpreter> : <version>
   - ...

3. Packages (per interpreter inspected)
   - torch:        <version or "absent">
   - ultralytics:  <version or "absent">
   - cv2:          <version or "absent">
   - numpy:        <version or "absent">
   - PyYAML:       <version or "absent">

4. Torch / CUDA
   - torch.version.cuda:        <value or n/a>
   - torch.cuda.is_available(): <True/False/n/a>
   - CUDA-capable build?        <yes/no>

5. GPU / driver
   - GPU name:     <value or "unavailable">
   - Driver:       <value>
   - VRAM total/free: <value>

6. Resources
   - RAM total/free:  <value>
   - Disk free (workspace drive): <value>

7. Divergence from TRD §17
   <none | details>

8. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

9. Limitations / honesty note
   <what was measured; what was NOT changed or created>

10. Result: COMPLETE / BLOCKED / STOPPED
    Next phase authorised? YES / NO (awaiting approval)
```
