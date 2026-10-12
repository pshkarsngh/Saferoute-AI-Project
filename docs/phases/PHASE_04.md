# SafeRoute AI — Phase 04: Workspace Virtual Environment & Dependencies

> **Phase ID:** PHASE_04
> **Status:** Not started — awaiting explicit approval
> **Predecessor:** [`PHASE_03`](./PHASE_03.md) — Dataset Integrity, Class-Mapping & Split Audit
> **Successor:** [`PHASE_05`](./PHASE_05.md) — CUDA / GPU & Training-Readiness Verification
> **Index:** [`README.md`](./README.md)
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Objective

Create a **workspace-local, isolated, reproducible Python environment** with pinned
dependencies for the SafeRoute AI toolchain: Python 3.12, CUDA-enabled PyTorch (if the GPU and
driver permit), Ultralytics YOLO11, OpenCV, and supporting libraries. Record exact versions
(gates **G10**) so every later run is reproducible.

This phase **installs software** and therefore requires explicit user approval (Rule 19). It
must **not** download datasets or checkpoints, and must **not** start training.

---

## 2. Scope

### In scope
- Create `D:\New folder (3)\.venv` using **Python 3.12**.
- Install pinned dependencies into `.venv` only (no global installs) (Rule 1, Rule 18).
- Prefer a **CUDA-enabled** PyTorch build matched to the GPU/driver; if not possible, install
  CPU-only and record the limitation (do not pretend CUDA works).
- Install Ultralytics (YOLO11) and OpenCV.
- Create `requirements.txt` and `requirements-dev.txt`; record a lock (`pip freeze`).
- Create `.env.example` (placeholder only) and update `.gitignore` to exclude secrets,
  `.venv/`, data, models, logs and caches.

### Out of scope
- Downloading pretrained checkpoints (PHASE_07, needs its own approval).
- Training (PHASE_08).
- Creating credentials or `.env` with real secrets (Rule 13).
- Modifying datasets (Rule 19).

---

## 3. Prerequisites

| # | Prerequisite | Notes |
|---|---|---|
| P1 | PHASE_01 environment audit accepted | Know available interpreters/GPU |
| P2 | PHASE_03 complete | Dataset audited (environment can proceed in parallel only if approved) |
| P3 | User approves installing packages | Rule 19 |
| P4 | A Python 3.12 interpreter is available (or user approves installing one) | Record choice |

---

## 4. Detailed procedure

1. **Confirm the Python version decision.** Use **3.12** unless the user approves another
   version. Do not change the system default interpreter.
2. **Create the venv inside the workspace:**
   ```
   py -3.12 -m venv "D:\New folder (3)\.venv"
   ```
   Confirm `.venv` resides inside the workspace (Rule 1).
3. **Record the interpreter identity:** `python --version`, path, architecture.
4. **Write `requirements.txt` with pinned versions** (exact pins chosen and recorded):
   - CUDA-enabled PyTorch (`torch`, `torchvision`) matched to the GPU/driver — or CPU-only
     with the limitation recorded;
   - `ultralytics` (YOLO11);
   - `opencv-python`;
   - `numpy`, `PyYAML`;
   - runtime packages for later phases (e.g. `fastapi`, `uvicorn`) — install only if approved
     now; otherwise defer to their phase.
5. **Install into `.venv` only.** Record the exact commands and their real output.
   ```
   "D:\New folder (3)\.venv\Scripts\python.exe" -m pip install --upgrade pip
   "D:\New folder (3)\.venv\Scripts\python.exe" -m pip install -r requirements.txt
   ```
6. **Verify imports (no training):**
   - `import torch, ultralytics, cv2, numpy, yaml`;
   - print versions.
7. **Record the lock file:** `pip freeze > requirements-lock.txt` inside the workspace.
8. **Create `.env.example`** with placeholder variable names only (no real values) and confirm
   `.gitignore` excludes `.venv/`, `.env`, `data/`, `models/`, `logs/`, caches (Rule 13, §3.3).
9. **Do not download model weights.** Ultralytics package installation is allowed; downloading
   a pretrained checkpoint is deferred to PHASE_07 with separate approval.
10. **Write the completion report** (§11).

---

## 5. Approval gates

| Gate | Requirement |
|---|---|
| A1 | User approves starting PHASE_04. |
| A2 | User approves the **exact** package list and versions before installation (Rule 19). |
| A3 | If CUDA-enabled builds require a large download, user approves the download. |
| A4 | Creating `.env` with real secrets or any credentials is **out of scope** and separately approved (Rule 13). |
| A5 | Downloading pretrained model weights is **out of scope** (PHASE_07). |

---

## 6. Validation checks

| # | Check | Pass condition |
|---|---|---|
| V1 | Venv location | `.venv` is inside `D:\New folder (3)`. |
| V2 | Interpreter version | `.venv` Python is 3.12 (or approved alternative). |
| V3 | Isolation | Installs occurred only in `.venv`; no global packages changed. |
| V4 | Imports succeed | `torch`, `ultralytics`, `cv2`, `numpy`, `yaml` import without error. |
| V5 | Versions recorded | Exact versions logged (G10). |
| V6 | Lock file | `requirements-lock.txt` created and matches installed set. |
| V7 | Secrets hygiene | `.env.example` has placeholders only; `.env`/`.venv` excluded by `.gitignore`. |
| V8 | No forbidden downloads | No dataset or model checkpoint downloaded. |

---

## 7. Acceptance criteria

- [ ] A workspace-local `.venv` exists on Python 3.12.
- [ ] All required packages import successfully within `.venv`.
- [ ] `requirements.txt` and `requirements-lock.txt` exist with real, pinned versions.
- [ ] `.env.example` and `.gitignore` are correct and secret-free.
- [ ] The CUDA vs CPU nature of the installed torch is recorded truthfully.
- [ ] Completion report submitted and accepted.

---

## 8. Stop conditions

Stop and report if:
1. A chosen package cannot be installed with a compatible version set.
2. Installation would require modifying the system Python or a global site-packages
   (Rule 1, Rule 18).
3. A CUDA-enabled torch cannot be installed for the actual GPU/driver (record as a limitation;
   do not claim CUDA).
4. Any install would write outside the workspace `.venv` (Rule 1).
5. A secret or credential would need to be stored outside `.env` (Rule 13).

---

## 9. Traceability

| Rule / requirement | Where addressed |
|---|---|
| Rule 1 Isolation | §4.2, V1, V3, §8.4 |
| Rule 13 Security | §4.8, V7, §8.5 |
| Rule 16 Hardware-aware build | §4.4, §4.7 |
| Rule 17 Documentation | §4.5, §4.7, V5–V6 |
| Rule 18 Minimal changes | §2 out-of-scope, V3 |
| Rule 19 No unauthorized actions | §5, V8 |
| TRD §3.2–§3.3 | Whole phase |
| TRAINING_RULES §2 G10 | §4.5, V5 |

---

## 10. Honesty note

Installing packages does **not** mean the environment is training-ready. CUDA availability is
verified separately in PHASE_05. Do not claim GPU training works until verified.

---

## 11. Completion report template

```
PHASE_04 — Completion Report
============================
Date (actual):           <YYYY-MM-DD>
Approval reference:      <user approval of package list>

1. Environment
   - Venv path:          D:\New folder (3)\.venv
   - Python version:     <x.y.z>
   - Inside workspace?   <yes>

2. Commands run (exact)
   <list>

3. Installed versions
   - torch:        <version> (<cuda/cpu>)
   - ultralytics:  <version>
   - opencv:       <version>
   - numpy:        <version>
   - PyYAML:       <version>
   - other:        <...>

4. Files created
   - requirements.txt:        <path>
   - requirements-lock.txt:   <path>
   - .env.example:            <path>
   - .gitignore:              <path/updated>

5. CUDA status of installed torch
   - torch.version.cuda: <value or n/a>
   - build type:         CUDA / CPU-only

6. Validation results
   V1 <pass/fail + evidence> ... V8 <pass/fail + evidence>

7. Forbidden actions check (must all be "none")
   - dataset downloads: none / <details>
   - model downloads:   none / <details>
   - training runs:     none / <details>
   - global installs:   none / <details>

8. Limitations / honesty note
   <e.g. CPU-only torch installed; CUDA not yet verified>

9. Result: COMPLETE / BLOCKED / STOPPED
   Next phase authorised? YES / NO (awaiting approval)
```
