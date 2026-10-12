# PHASE_04 — Completion Report: Workspace Virtual Environment & Dependencies

> **Phase ID:** PHASE_04
> **Status:** COMPLETE
> **Date (actual):** 2026-10-12
> **Workspace:** `D:\New folder (3)`
> **Predecessor:** [`PHASE_03`](./PHASE_03_report.md) — Dataset Integrity, Class-Mapping & Split Audit
> **Successor:** PHASE_05 — CUDA / GPU & Training-Readiness Verification
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Approval reference

| Gate | Requirement | Approval |
|---|---|---|
| A1 | Start PHASE_04 | **Approved** by user |
| A2 | Exact package list and versions (+ D1–D6) | **Approved** by user |
| A3 | ~1.84 GB CUDA-enabled PyTorch/TorchVision download | **Approved** by user |

Decisions applied: **D1** `opencv-python==4.14.0.94`; **D2** `requirements-dev.txt` header-only;
**D3** FastAPI/Uvicorn deferred; **D4** Ultralytics settings inside the workspace;
**D5** `.gitignore` add `models/`, `logs/`, `data/`, `.ultralytics/` (no untracking);
**D6** `--no-cache-dir` for all pip installs.

---

## 2. Environment

- **Venv path:** `D:\New folder (3)\.venv`
- **Inside workspace?** Yes (Rule 1)
- **Interpreter:** `D:\New folder (3)\.venv\Scripts\python.exe`
- **Python version:** 3.12.10 — `3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]`
- **pip version:** 26.2.1 (upgraded from 25.0.1 inside the venv)
- **Free disk on `D:` before install:** 82.4 GB

---

## 3. Commands run (exact)

Pre-flight (read-only):

```powershell
py -3.12 --version                                  # Python 3.12.10
Test-Path "D:\New folder (3)\.venv"                 # False
Get-PSDrive D | Select-Object Name,@{n='Free_GB';e={[math]::Round($_.Free/1GB,1)}}
```

Environment creation and installs:

```powershell
py -3.12 -m venv "D:\New folder (3)\.venv"
"D:\New folder (3)\.venv\Scripts\python.exe" -m pip install --upgrade pip --no-cache-dir
"D:\New folder (3)\.venv\Scripts\python.exe" -m pip install --no-cache-dir "torch==2.13.0+cu130" "torchvision==0.28.0+cu130" --index-url https://download.pytorch.org/whl/cu130
"D:\New folder (3)\.venv\Scripts\python.exe" -m pip install --no-cache-dir "ultralytics==8.4.163" "opencv-python==4.14.0.94" "numpy==2.5.3" "PyYAML==6.0.3"
```

Lock file:

```powershell
"D:\New folder (3)\.venv\Scripts\python.exe" -m pip freeze   # → requirements-lock.txt (40 packages)
```

Verification (compute-only; no training):

```powershell
$env:YOLO_CONFIG_DIR = "D:\New folder (3)\.ultralytics"
"D:\New folder (3)\.venv\Scripts\python.exe" -c "import torch,torchvision,ultralytics,cv2,numpy,yaml; print(...)"
"D:\New folder (3)\.venv\Scripts\python.exe" -c "import torch; ...; a=torch.rand(1024,1024,device='cuda'); ..."
```

Actual outputs:

```text
torch 2.13.0+cu130
torch.version.cuda 13.0
cuda.is_available True
torchvision 0.28.0+cu130
ultralytics 8.4.163
cv2 4.14.0
numpy 2.5.3
yaml 6.0.3

cuda_available True
count 1
name NVIDIA GeForce RTX 5050 Laptop GPU
cc 12.0
total_MiB 8123.4
free_MiB 7070.0
arch_list ['sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']
gpu_op_ok 267710608.0
allocated_MiB 36.0
```

---

## 4. Installed versions (direct pins)

| Package | Required pin | Installed |
|---|---|---|
| torch | `2.13.0+cu130` | **2.13.0+cu130** |
| torchvision | `0.28.0+cu130` | **0.28.0+cu130** |
| ultralytics | `8.4.163` | **8.4.163** |
| opencv-python | `4.14.0.94` | **4.14.0.94** (`cv2.__version__` = 4.14.0) |
| numpy | `2.5.3` | **2.5.3** (a transitive 2.5.2 was superseded by the pin) |
| PyYAML | `6.0.3` | **6.0.3** |
| pip | — | 26.2.1 |

Downloaded wheels: `torch-2.13.0+cu130-cp312-cp312-win_amd64.whl` (1915.5 MB),
`torchvision-0.28.0+cu130-cp312-cp312-win_amd64.whl` (9.1 MB), plus the pinned PyPI
packages and transitive dependencies (see `requirements-lock.txt`).

---

## 5. CUDA status of installed torch

- `torch.version.cuda`: **13.0**
- Build type: **CUDA** (`+cu130`) — not the CPU-only PyPI wheel
- `torch.cuda.is_available()`: **True**
- Device: **NVIDIA GeForce RTX 5050 Laptop GPU**, compute capability **12.0 (sm_120)**
- `torch.cuda.get_arch_list()` includes `sm_120` (Blackwell)
- Real GPU tensor op executed successfully; VRAM total 8123.4 MiB, free 7070.0 MiB at test time

Driver-side context (from PHASE_05 Blocks A–C): NVIDIA KMD **616.64**, CUDA UMD **13.4**
(≥ R580 branch), which satisfies the CUDA 13.0 requirement.

---

## 6. Files created / modified

**Created:**

| Path | Purpose |
|---|---|
| `D:\New folder (3)\.venv\` | Workspace-local Python 3.12 virtual environment |
| `D:\New folder (3)\requirements.txt` | Exact approved pins (with cu130 index line) |
| `D:\New folder (3)\requirements-dev.txt` | Header-only (D2) |
| `D:\New folder (3)\requirements-lock.txt` | `pip freeze` of the installed environment (40 packages) |
| `D:\New folder (3)\.env.example` | Placeholder variable names only; no real values |
| `D:\New folder (3)\.ultralytics\Ultralytics\settings.json` | Ultralytics first-run settings (kept inside the workspace, D4) |
| `D:\New folder (3)\docs\reports\PHASE_04_report.md` | This report |

**Modified:**

| Path | Change |
|---|---|
| `D:\New folder (3)\.gitignore` | Appended `models/`, `logs/`, `data/`, `.ultralytics/` (D5). No existing rules removed; no files untracked. |

No dataset, model weights, `config/`, `src/`, `frontend/`, `tests/`, `models/` or `logs/`
were created (those belong to later phases).

---

## 7. Validation results

| # | Check | Result | Evidence |
|---|---|---|---|
| V1 | Venv location | **PASS** | `.venv` is inside `D:\New folder (3)` |
| V2 | Interpreter version | **PASS** | Python 3.12.10 |
| V3 | Isolation | **PASS** | All installs used the venv interpreter; no global site-packages touched |
| V4 | Imports succeed | **PASS** | `torch, torchvision, ultralytics, cv2, numpy, yaml` all imported |
| V5 | Versions recorded | **PASS** | §4 + `requirements-lock.txt` (G10) |
| V6 | Lock file | **PASS** | `requirements-lock.txt` generated from the installed environment |
| V7 | Secrets hygiene | **PASS** | `.env.example` has placeholders only; `.gitignore` excludes `.env` and `.venv/` |
| V8 | No forbidden downloads | **PASS** | No dataset or model checkpoint downloaded |

G10 (environment recorded): **PASS**. (G11/G12 are PHASE_05 gates; see §10.)

---

## 8. Deviations & remediation

1. **Ultralytics settings directory.** On the first import check, this Ultralytics version
   (`8.4.163`) resolves its config dir as `YOLO_CONFIG_DIR\Ultralytics`. Because the workspace
   parent `D:\New folder (3)\.ultralytics` did not yet exist, it declared the path non-writable
   and created settings at `C:\Users\ASUS\Ultralytics\settings.json` — **outside** the workspace.
   **Remediated:** the workspace directory `D:\New folder (3)\.ultralytics` was pre-created and
   the stray outside-workspace `C:\Users\ASUS\Ultralytics` (created only by that run) was removed.
   Subsequent imports write to `D:\New folder (3)\.ultralytics\Ultralytics\settings.json`. Rule 1
   restored and verified.
2. **numpy transitive version.** The `torch`/`torchvision` install first pulled `numpy 2.5.2`;
   the approved pin `numpy==2.5.3` was then installed (2.5.2 uninstalled). Final state is 2.5.3.

---

## 9. Forbidden-actions check

- dataset downloads: **none**
- model/checkpoint downloads: **none**
- training runs: **none**
- global installs: **none**
- driver updates: **none**
- dataset modifications: **none**
- pip cache outside workspace: **none** (`--no-cache-dir` used throughout)

---

## 10. Limitations / honesty note

Installing packages does **not** by itself mean the environment is training-ready. This phase
records an environment in which `torch.cuda.is_available()` is `True` and a real GPU tensor op
succeeded; that is a measurement, not a training result. Formal CUDA/driver and resource gating
(G11/G12) remains PHASE_05. As of this report, PHASE_05 Blocks A–C (driver/GPU/CUDA evidence)
have passed; Block D (post-install torch/Ultralytics verification) may now be run under its own
approval. No training has occurred and no metrics exist.

---

## 11. Result

**PHASE_04: COMPLETE** — all required checks (§7) passed.

**Next phase authorised?** NO — awaiting explicit approval.
