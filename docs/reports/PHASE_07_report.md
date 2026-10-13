# PHASE_07 — Completion Report: YOLO11 Baseline Training Plan & Config Freeze

> **Phase ID:** PHASE_07  
> **Status:** COMPLETE  
> **Date (actual):** 2026-10-13  
> **Workspace:** `D:\New folder (3)`  
> **Model Version Identifier:** `saferoute-yolo11-v1`  
> **Predecessor:** [`PHASE_06`](./PHASE_06_report.md) — OpenCV Preprocessing & Image-Quality Pipeline  
> **Successor:** [`PHASE_08`](../phases/PHASE_08.md) — YOLO11 Baseline Training Run  
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../TRAINING_RULES.md`](../TRAINING_RULES.md)

---

## 1. Dataset YAML Configuration

- **File Path:** [`data/dataset.yaml`](../../data/dataset.yaml)
- **Root Path:** `../data/pothole_crack_manhole/data` (workspace-isolated)
- **Split Definitions:**
  - `train`: `../../splits/train.txt` (1,406 images)
  - `val`: `../../splits/val.txt` (402 images)
  - `test`: `../../splits/test.txt` (201 images)
- **Names Mapping:**
  ```yaml
  names:
    0: pothole
    1: crack
  ```

---

## 2. Class Mapping (from PHASE_03 Audit)

| Class ID | Actual Dataset Label | Status in SafeRoute YOLO11 | Action |
|---|---|---|---|
| `0` | `pothole` | Supported | Trained as target class 0 |
| `1` | `crack` | Supported | Trained as target class 1 |
| `2` | `manhole` | Unsupported | Excluded from target classes; never relabelled |

---

## 3. Split Manifest Reference & Distribution

- **Manifest File:** [`reports/phase03/split_manifest_proposal_sessionaware_v2_strict30s.csv`](../../reports/phase03/split_manifest_proposal_sessionaware_v2_strict30s.csv)
- **Split Index Files:** Created under [`data/splits/`](../../data/splits/):
  - `train.txt`: 1,406 images (~70.0%)
  - `val.txt`: 402 images (~20.0%)
  - `test.txt`: 201 images (~10.0%)
- **Total Images Indexed:** 2,009 (100% of audited dataset accounted for)
- **Temporal & Session Separation:** Strict-30s session clustering ensures adjacent sequential frames from same recording sessions are not split across train and test sets.

---

## 4. Baseline Architecture Decision

- **Chosen Variant:** **`YOLO11n`** (Nano baseline detector)
- **Technical Rationale:** Smallest, fastest parameter architecture (~2.6M params). Enables rapid training iterations, minimal VRAM/RAM overhead, and fast edge inference for real-time dashcam/street imagery processing. Larger variants (`YOLO11s` / `YOLO11m`) are explicitly deferred until baseline convergence is proven.

---

## 5. Pretrained Checkpoint Provenance (NOT Downloaded in this Phase)

- **Target Weights:** `yolo11n.pt`
- **Official Source:** Ultralytics Assets Release (`https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt`)
- **Licence:** AGPL-3.0 / Ultralytics Enterprise
- **Compatibility:** Fully compatible with installed Ultralytics 8.4.163 and PyTorch 2.13.0+cu130
- **Status:** **Download pending explicit user approval in Phase 08** (no weights downloaded in Phase 07).

---

## 6. Hyperparameter Envelope (PROVISIONAL — Justified by Phase 05 Headroom)

Configuration frozen in [`config/training_baseline.yaml`](../../config/training_baseline.yaml):

| Parameter | Frozen Value | Rationale & Measurement Source |
|---|---|---|
| `imgsz` | `640` | Standard YOLO dimension matching OpenCV letterbox transform |
| `batch` | `16` | Measured in Phase 05: 8,123 MB total VRAM with ~7.0 GB free |
| `epochs` | `50` | Initial baseline convergence ceiling |
| `patience` | `10` | Early stopping to prevent catastrophic overfitting |
| `amp` | `true` | Mixed precision FP16 (CUDA compute 12.0 verified) |
| `workers` | `2` | Conservative setting to protect limited ~1.4 GB host free RAM |
| `optimizer` | `auto` | AdamW / SGD adaptive selection |
| `seed` | `42` | Fixed seed for reproducible run execution |
| `device` | `0` | CUDA device index 0 (`NVIDIA GeForce RTX 5050 Laptop GPU`) |

---

## 7. Reproducibility Capture Protocol

During execution in Phase 08, the training script will log:
1. Exact CLI execution command and working directory.
2. Python interpreter path and version (`Python 3.12.10`).
3. Installed package lockfile snapshot (`requirements-lock.txt`).
4. Git commit SHA of the codebase before training starts.
5. Random seed (`42`) and deterministic PyTorch/CUDNN flags.
6. Dataset manifest SHA256 and config hashes.
7. Full epoch metrics log (`results.csv`) and TensorBoard / Ultralytics run logs.

---

## 8. Output & Checkpoint Directories

All output paths are strictly workspace-isolated per Rule 1:
- **Model Checkpoints:** `models/training/saferoute-yolo11-v1/weights/` (`best.pt`, `last.pt`, `epoch*.pt`)
- **Training Metrics & Curves:** `models/training/saferoute-yolo11-v1/` (`results.png`, `confusion_matrix.png`, etc.)
- **Execution Logs:** `logs/training/saferoute-yolo11-v1/`

---

## 9. Evaluation Plan Reference

The quantitative and qualitative acceptance plan is frozen in [`docs/evaluation_plan.md`](../evaluation_plan.md):
- **Metrics Tracked:** Precision, Recall, F1, mAP@0.5, mAP@0.5:0.95 (overall and per class).
- **Test Isolation:** Held-out test set (`data/splits/test.txt`, 201 images) is untouched during training.
- **Qualitative Review:** 20 held-out test visualisations rendered to `logs/evaluation/qualitative_samples/`.

---

## 10. Training Gate Re-check Status (G1–G13 Pre-Flight)

| Gate | Description | Status | Evidence Source |
|---|---|:---:|---|
| **G1** | Provenance & Licence | **PASS** | `PHASE_02_report.md` (CC BY 4.0 Zenodo record 18528034) |
| **G2** | Dataset Location | **PASS** | `PHASE_02_report.md` (`D:\New folder (3)\data\...`) |
| **G3** | Pairing Audit | **PASS** | `PHASE_03_report.md` (2,009/2,009 images paired) |
| **G4** | Class Distribution | **PASS** | `PHASE_03_report.md` (pothole: 1,261, crack: 2,519) |
| **G5** | Image Integrity | **PASS** | `PHASE_03_report.md` (0 corrupt, 0 empty in dataset) |
| **G6** | Annotation Format | **PASS** | `PHASE_03_report.md` (YOLO format validated) |
| **G7** | Duplicate Detection | **PASS** | `reports/phase03/split_leakage_review_v1.md` |
| **G8** | Split Separation | **PASS** | `data/splits/` session-aware strict 30s split files |
| **G9** | Path Safety | **PASS** | `data/dataset.yaml` uses relative workspace paths |
| **G10** | Preprocessing Contract | **PASS** | `PHASE_06_report.md` (`src.preprocessing` v1) |
| **G11** | GPU / CUDA Availability | **PASS** | `PHASE_05_report.md` (CUDA 13.0, RTX 5050 8GB) |
| **G12** | Resource Headroom | **PASS** | `PHASE_05_report.md` (79 GB disk free, ~7 GB VRAM) |
| **G13** | Baseline Plan Recorded | **PASS** | `config/training_baseline.yaml` & this report |

---

## 11. Validation Results Summary

| # | Check | Pass Condition | Status | Evidence |
|---|---|---|:---:|---|
| V1 | Dataset YAML valid | `path`/`train`/`val`/`test`/`names` present | **PASS** | `data/dataset.yaml` verified by python script |
| V2 | Class mapping consistent | Matches PHASE_03 mapping | **PASS** | 0: pothole, 1: crack |
| V3 | Split manifest referenced | Manifest available and consistent | **PASS** | `data/splits/*.txt` matches 1406/402/201 |
| V4 | Test isolation stated | Evaluation plan isolates test set | **PASS** | Documented in `docs/evaluation_plan.md` |
| V5 | Variant recorded | YOLO11n recorded with rationale | **PASS** | Recorded in `config/training_baseline.yaml` |
| V6 | Checkpoint provenance | Source & licence recorded | **PASS** | Recorded (download pending Phase 08) |
| V7 | Settings justified | Values tied to measured constraints | **PASS** | `batch=16`, `workers=2`, `imgsz=640` |
| V8 | Paths inside workspace | All paths inside `D:\New folder (3)` | **PASS** | Verified workspace paths |
| V9 | No training / download | Neither occurred in this phase | **PASS** | Configuration and planning only |

---

## 12. Conclusion & Next Steps

- **Result:** **COMPLETE**
- **Next Phase Authorised?** **NO** — awaiting explicit user review and approval before starting [`PHASE_08`](../phases/PHASE_08.md) (YOLO11 Baseline Training Run).
