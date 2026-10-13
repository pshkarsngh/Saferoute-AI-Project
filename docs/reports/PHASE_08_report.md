# PHASE_08 — Baseline Training Run Report: YOLO11n Baseline Training Run

> **Phase ID:** PHASE_08  
> **Status:** COMPLETE  
> **Date (actual):** 2026-10-13  
> **Workspace:** `D:\New folder (3)`  
> **Model Version Identifier:** `saferoute-yolo11-v1`  
> **Predecessor:** [`PHASE_07`](./PHASE_07_report.md) — YOLO11 Baseline Training Plan & Config Freeze  
> **Successor:** [`PHASE_09`](../phases/PHASE_09.md) — Model Evaluation & Checkpoint Acceptance  
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md) · [`../phases/PHASE_08.md`](../phases/PHASE_08.md)  
> **Approval Reference:** User explicit directive `complete phase 08` (2026-10-13)

---

## 1. Gate Confirmation (G1–G13 Pre-Flight Re-check)

All gates re-confirmed with empirical evidence immediately prior to training launch:

| Gate | Description | Status | Evidence / Verification Source |
|---|---|:---:|---|
| **G1** | Dataset Provenance & Licence | **PASS** | Zenodo record 18528034 (`data.zip` MD5: `317862054545467FF00BE611DB8FF07E`), CC BY 4.0 |
| **G2** | Dataset Location | **PASS** | Strictly inside workspace: `D:\New folder (3)\data\pothole_crack_manhole\data` |
| **G3** | File Count | **PASS** | 2,009 paired images in dataset (train: 1,406, val: 402, test: 201) |
| **G4** | Images Readable | **PASS** | 2,009/2,009 decodable, 0 corrupt images found during audit |
| **G5** | Annotations Valid | **PASS** | YOLO bounding boxes normalized and within [0, 1] |
| **G6** | Format & Class Mapping | **PASS** | YOLO format; target classes: `0: pothole`, `1: crack`; `2: manhole` (unsupported, excluded) |
| **G7** | Data Hygiene Audit | **PASS** | 0 empty labels among targets, split leakage audited in Phase 03 |
| **G8** | Split Separation | **PASS** | Strict-30s session separation manifest referenced; split index files in `data/splits/` |
| **G9** | Test Isolation | **PASS** | `data/splits/test.txt` (201 images) held out untouched; zero test exposure during training |
| **G10** | Environment Recorded | **PASS** | Python 3.12.10, PyTorch 2.13.0+cu130, Ultralytics 8.4.163, OpenCV 4.14.0 |
| **G11** | GPU / CUDA Verified | **PASS** | `torch.cuda.is_available() == True`, NVIDIA GeForce RTX 5050 Laptop GPU (compute 12.0) |
| **G12** | Resources Headroom | **PASS** | Pre-run: 7,070 MB free VRAM (out of 8,123 MB), 14.3 GB free disk space, 4,744 MB free host RAM |
| **G13** | Baseline Plan Recorded | **PASS** | Frozen configuration in `config/training_baseline.yaml` (SHA256: `D08854428D8889CB5B362B001730DD81985207820D5F6D5FA03CC772D70B9D52`) |

---

## 2. Reproducibility Record

- **Dataset Path:** `D:/New folder (3)/data/pothole_crack_manhole/data`
- **Dataset YAML Hash (SHA-256):** `CD502CDC20B732CBBE239A6F80FBA69CFD4B9451CFBE5BA26EC2AC0687E5969E`
- **Class Mapping:**
  - `0`: `pothole` (Supported target class)
  - `1`: `crack` (Supported target class)
  - `2`: `manhole` (Unsupported; excluded per Phase 03 decision, never relabelled)
- **Split Files & Hashes (SHA-256):**
  - Train (`data/splits/train.txt`, 1,406 images): `47042901B46064F16D012DB66FBA388F73889482F2E36DB6E179BADE7329800C`
  - Val (`data/splits/val.txt`, 402 images): `13D992B1383665DA40970CD466B4FA125902250608B7178C859E52EDDB48B215`
  - Test (`data/splits/test.txt`, 201 images): `46F647E0C102C88E2500F6304AD3F3FB9AE106B7060CEE12302A85887A42CA51` *(Untouched)*
- **Git Commit SHA:** `09bdd8ceb316b15fb8d2521ac03efa9489a08b0b`
- **Software Stack:**
  - Python: `3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]`
  - PyTorch: `2.13.0+cu130`
  - CUDA Build: `13.0`
  - Ultralytics: `8.4.163`
  - OpenCV: `4.14.0`
  - OS / Platform: `Windows-11-10.0.26300-SP0`
  - NVIDIA Driver: `616.64`
- **Hardware Profile:**
  - Compute Device: `NVIDIA GeForce RTX 5050 Laptop GPU` (Device Index `0`, Compute Capability `12.0`)
  - Dedicated VRAM: 8,123.44 MB total (~8.0 GB)
- **Model Variant:** `YOLO11n` (Nano baseline architecture, 2,582,542 parameters)
- **Pretrained Checkpoint Provenance:**
  - Checkpoint: `yolo11n.pt` (Workspace root: `D:\New folder (3)\yolo11n.pt`)
  - Source: Ultralytics Assets Release v8.3.0 (`https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt`)
  - Licence: AGPL-3.0 / Ultralytics Enterprise
  - Pretrained Checkpoint Hash (SHA-256): `0EBBC80D4A7680D14987A577CD21342B65ECFD94632BD9A8DA63AE6417644EE1`

---

## 3. Execution Command (Exact)

Executed within the workspace virtual environment (`.venv`):

```powershell
.\.venv\Scripts\python.exe scripts\train_baseline.py
```

Underlying Ultralytics training call executed:
```python
model = YOLO("D:/New folder (3)/yolo11n.pt")
model.train(
    data="D:/New folder (3)/data/dataset.yaml",
    epochs=50,
    imgsz=640,
    batch=16,
    patience=10,
    optimizer="auto",
    lr0=0.01,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=3.0,
    warmup_momentum=0.8,
    warmup_bias_lr=0.1,
    box=7.5,
    cls=0.5,
    dfl=1.5,
    amp=True,
    seed=42,
    deterministic=True,
    workers=2,
    device=0,
    save_period=5,
    project="D:/New folder (3)/models/training",
    name="saferoute-yolo11-v1",
    exist_ok=True,
    val=True,
    plots=True,
    save=True,
)
```

---

## 4. Effective Settings

All parameters strictly mirror `config/training_baseline.yaml`:

| Setting | Value | Rationale |
|---|---|---|
| `imgsz` | `640` | Standard YOLO dimension matching OpenCV letterbox transform |
| `batch` | `16` | Sized to fit 8 GB VRAM with headroom |
| `epochs` | `50` | Maximum baseline training budget |
| `patience` | `10` | Early stopping patience |
| `optimizer` | `auto` | Selected AdamW / SGD automatically |
| `lr0` / `lrf` | `0.01` / `0.01` | Initial and final learning rate schedules |
| `momentum` / `weight_decay` | `0.937` / `0.0005` | Standard momentum and L2 regularization |
| `warmup_epochs` | `3.0` | Learning rate warmup stabilization |
| `amp` | `True` | Mixed precision FP16 on CUDA compute 12.0 |
| `seed` / `deterministic` | `42` / `True` | Fixed seed for reproducible run execution |
| `workers` | `2` | Conservative multi-process dataloading to preserve host RAM |
| `device` | `0` | CUDA device index 0 (RTX 5050 Laptop GPU) |
| `save_period` | `5` | Checkpoint persistence every 5 epochs |

---

## 5. Run Outcome

- **Status:** **`COMPLETED`**
- **Start Time (UTC):** `2026-10-13T15:21:57.381279+00:00`
- **End Time (UTC):** `2026-10-13T15:30:30.764684+00:00`
- **Elapsed Duration:** `513.35 seconds` (**8.56 minutes**)
- **Epochs Completed:** **49 epochs** (EarlyStopping triggered at epoch 49 because no improvement was observed for 10 epochs after peak at epoch 39; best weights persisted as `best.pt`)
- **Warnings / Errors:** None. Zero OOM errors, zero CUDA crashes, zero divergent losses.
- **Resource Peak:** VRAM allocation remained stable under 3.5 GB throughout execution; host RAM remained within safety bounds.

---

## 6. Artefacts & Integrity

All outputs reside strictly inside the workspace per Rule 1:

| Artefact | Workspace Path | SHA-256 Hash | Notes |
|---|---|---|---|
| **Best Checkpoint** | `models/training/saferoute-yolo11-v1/weights/best.pt` | `61F6EDA2B7ABBF12B87355B1E0871F4B9F0435C3D68762AF89C5349908078E65` | Checkpoint from epoch 39 |
| **Last Checkpoint** | `models/training/saferoute-yolo11-v1/weights/last.pt` | `2D4F2E3B7168FB2C7CEC9298F456406721C49FFF4C1264722208FE1908A1ABAD` | Final epoch 49 checkpoint |
| **Periodic Checkpoints** | `models/training/saferoute-yolo11-v1/weights/epoch*.pt` | Recorded on disk | Saved at epochs 0, 5, 10, 15, 20, 25, 30, 35, 40, 45 |
| **Training Log** | `logs/training/saferoute-yolo11-v1/train.log` | Recorded on disk | Full verbatim stdout/stderr run telemetry |
| **Run Record** | `logs/training/saferoute-yolo11-v1/run_record.json` | Recorded on disk | Machine-readable reproducibility manifest |
| **Curves & Metrics** | `models/training/saferoute-yolo11-v1/results.csv`, `results.png`, `confusion_matrix.png` | Recorded on disk | Epoch losses, PR curves, and confusion plots |
| **Prior Artefacts** | All previous files across `data/`, `reports/`, `src/` intact | N/A | No prior checkpoints or logs deleted |

---

## 7. Deviations from Plan

- **None.** The run executed strictly per the frozen configuration `config/training_baseline.yaml`. Early stopping at epoch 49 was fully expected and governed by the frozen parameter `patience: 10`.

---

## 8. Validation Results

| # | Check | Pass Condition | Status | Evidence |
|---|---|---|:---:|---|
| **V1** | Gates confirmed | G1–G13 all pass with recorded evidence | **PASS** | Re-confirmed and documented in §1 |
| **V2** | Isolation | No path resolves outside workspace | **PASS** | All inputs, checkpoints, and logs are inside `D:\New folder (3)` |
| **V3** | Reproducibility record | Versions, seed, settings, command captured | **PASS** | `logs/training/saferoute-yolo11-v1/run_record.json` |
| **V4** | Checkpoints saved | `best.pt` and `last.pt` exist at documented paths | **PASS** | Both verified with SHA-256 hashes in §6 |
| **V5** | Logs saved | Training logs exist in `logs/` | **PASS** | `logs/training/saferoute-yolo11-v1/train.log` |
| **V6** | Test untouched | No test-set evaluation performed | **PASS** | `data/splits/test.txt` was not loaded, evaluated, or touched |
| **V7** | No silent changes | Every deviation recorded with reason | **PASS** | Zero unrecorded deviations |
| **V8** | Prior artefacts intact | No prior checkpoint or log deleted | **PASS** | All prior records and phase reports preserved |

---

## 9. Limitations & Honesty Note (Rule 10, 14, 20)

- **Training execution completed; evaluation is NOT performed in this phase.**  
  Per Rule 14 and Phase 08 specification, a completed training run proves that training executed and converged without numerical instability or hardware failures. It does **not** assert real-world road-safety accuracy, production readiness, or model acceptance.
- **No test metrics claimed.**  
  Test set evaluation and acceptance criteria review are strictly out of scope for Phase 08 and will be conducted on the held-out test set (`data/splits/test.txt`) in **PHASE_09**.
- **Class Coverage Limitation:**  
  The trained model only detects `pothole` and `crack`. All other project hazard classes (`damaged_patch`, `waterlogging`, `uneven_surface`, `speed_bump`, `manhole`, etc.) remain untrained and unsupported in this baseline checkpoint.

---

## 10. Result & Phase Status

- **Result:** **`COMPLETE`**
- **Next Phase Authorised?** **`NO`** — awaiting explicit user review and approval before starting [`PHASE_09`](../phases/PHASE_09.md) (Model Evaluation & Checkpoint Acceptance).
