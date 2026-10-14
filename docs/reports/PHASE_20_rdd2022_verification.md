# PHASE_20 — Training Verification & RDD2022 Dataset Expansion (pre-download)

> **Status:** IN PROGRESS (download running, nothing merged, **no retraining**)
> **Date:** 2026-10-14 · **Workspace:** `D:\New folder (3)`
> **Governing:** master_rules.md (1, 3, 4, 5, 14, 15, 16, 17, 19, 20),
> docs/TRAINING_RULES.md §2 (G1–G13).
> **Approval:** user directive "Verify Training and Prepare Dataset Expansion"
> (this message) authorises the RDD2022 download subject to the stated conditions.

## 1. YOLO11 v2 training — VERIFIED

- **Status: COMPLETED** (early-stopped). No training process is running
  (no python/pythonw process found).
- Run record: `logs/training/saferoute-yolo11-v2/run_record.json`
  — `outcome.status = COMPLETED`, `end_utc 2026-10-13T22:46:04Z`,
  elapsed 1955.1 s (32.58 min), `error_message = null`.
- **Epochs completed: 144** (of 150). EarlyStopping (patience 40) triggered;
  **best epoch = 104**.
- Checkpoints (preserved, not modified):
  - best.pt → `models/training/saferoute-yolo11-v2/weights/best.pt`
    sha256 `B6354A562FDAF4B0A1498FDE2976930A94EAC8184083D0DD30342205DF8800BA`
  - last.pt → `models/training/saferoute-yolo11-v2/weights/last.pt`
    sha256 `58C4289F87DD12B5965F153088653EB9D2CFFDE20B686FCC21F0C349104AC132`
- Logs: `logs/training/v2_stdout.log`,
  `logs/training/saferoute-yolo11-v2/train.log`, `.../results.csv`.

### Validation metrics (validation split only — NOT the held-out test set)

Best.pt validation (epoch 104), measured by Ultralytics:

| Split | Scope | P | R | mAP@0.5 | mAP@0.5:0.95 |
|---|---|---|---|---|---|
| val | overall | 0.383 | 0.372 | **0.287** | 0.103 |
| val | pothole | 0.429 | 0.453 | 0.368 | 0.134 |
| val | crack | 0.331 | 0.292 | 0.206 | 0.071 |

- Per `run_record.json` the splits were train=1406 / val=402 / test=201 images.
- **v2 has NOT been evaluated on the held-out test split.** Per the task and
  TRAINING_RULES §6, **no claim of improved metrics vs v1 is made here.**
  (v1 test mAP@0.5 = 0.2615; v1 val mAP@0.5 = 0.2731 — for reference only.)

## 2. Environment (measured)

- Disk `D:` free: **91.26 GB** (total 660.56 GB).
- GPU: NVIDIA GeForce RTX 5050 Laptop, 8123 MiB VRAM (from run_record).
- No conflicting training running.

## 3. RDD2022 source & licence verification (before download)

- **Primary S3 link (from official sekilab README) is DEAD:** every
  `bigdatacup.s3...amazonaws.com/.../RDD2022*.zip` URL returns
  `HTTP 403 AccessDenied` (verified 2026-10-14). Not used.
- **Official mirror used:** FigShare record **21431547** —
  `RDD2022 - The multi-national Road Damage Dataset released through CRDDC'2022`,
  DOI `10.6084/m9.figshare.21431547.v1`.
- **Archive:** `RDD2022_released_through_CRDDC2022.zip`
  - size **13,264,172,619 bytes ≈ 12.35 GiB**
  - MD5 `b62bd51d2ffcfaa76c60f234f0cc2bb3` (record-supplied)
  - download `https://ndownloader.figshare.com/files/38030910` (302 → signed S3;
    ranged GET returns `206 Partial Content`, size confirmed).
- **Contents:** 47,420 images, 6 countries (Japan, India, Czech Republic,
  Norway, United States, China), >55,000 annotated road-damage instances.
- **Annotation format:** Pascal VOC **XML** (one `.xml` per image), train split
  only; test split is images-only.
- **Layout:** `RDD2022/<Country>/train/{images, annotations/xmls}` and
  `.../test/images`.
- **Classes** (`label_map.pbtxt`): `D00` longitudinal crack, `D10` transverse
  crack, `D20` alligator crack, `D40` pothole.

### Licence — RESOLVED (documented determination)

Actual source records:

| Source record | Stated licence |
|---|---|
| FigShare record 21431547 `license` field (host of the downloaded archive) | **CC BY 4.0** |
| sekilab `RoadDamageDetector` README, "License" section (dataset creators) | images **CC BY-SA 4.0** |
| sekilab repo `LICENSE` file | MIT (this covers **code only**, not the data) |

**Determination (this phase):** the two dataset statements conflict, so the project
adopts the **stricter CC BY-SA 4.0** for any use, derivative or redistribution,
and records the required attribution. This is a documented, conservative
decision — not a silent choice. Any redistribution/merge is gated on this
decision being accepted; local use with attribution is permitted under CC BY-SA
4.0. No data is redistributed by this project.

Required attribution string:
> RDD2022 — The multi-national Road Damage Dataset released through CRDDC'2022,
> Arya et al. (2022), figshare, DOI 10.6084/m9.figshare.21431547.v1,
> licensed CC BY-SA 4.0.

### Attribution / citation

> Arya, D., Maeda, H., Sekimoto, Y., et al. (2022). RDD2022 — The multi-national
> Road Damage Dataset released through CRDDC'2022. figshare.
> https://doi.org/10.6084/m9.figshare.21431547.v1
> (Data article: Arya et al., *Geoscience Data Journal* 11(4):846–862, 2024.)

## 4. Download

- Destination (workspace, existing data preserved):
  `data/raw/RDD2022/RDD2022_released_through_CRDDC2022.zip`
- Status: **running in background** at time of writing.

## 5. Proposed class mapping (to confirm after annotation audit)

Project classes (match `data/dataset.yaml` and detector `SUPPORTED_CLASSES`):
`0 = pothole`, `1 = crack`.

| RDD class | Meaning | Proposed project class | Action |
|---|---|---|---|
| `D40` | pothole | `0 pothole` | include |
| `D00` | longitudinal crack | `1 crack` | include |
| `D10` | transverse crack | `1 crack` | include |
| `D20` | alligator crack | `1 crack` | include (documented decision) |
| any other (`D43`,`D44`,…) | crosswalk/white-line blur | — | **excluded / unsupported**, never silently relabelled |

`manhole` (project class id 2) is absent from RDD2022 and remains unsupported.

## 6. Validation & leakage plan (before any merge/retrain)

1. Verify archive MD5 against `b62bd51d2ffcfaa76c60f234f0cc2bb3`.
2. Read-only audit of Pascal VOC XMLs: parse errors, out-of-range boxes,
   unknown class names, image/label pairing, per-class instance counts.
3. **Leakage control:** group images by capture **session/sequence** (from
   filename) and keep each group wholly within one split; also exact/near
   duplicate detection (sha256 + dHash) within and across the existing dataset.
4. Produce a versioned `dataset.yaml` + split manifests **in a NEW dataset
   version directory**; do not modify `data/pothole_crack_manhole` or the
   `data/splits/*.txt` used by v1/v2.
5. Only then produce a frozen, versioned training config.

## 7. Explicitly NOT done

- No retraining launched (step 7 gate not met).
- No metrics claimed for v2 on the held-out test set (step 8).
- No existing dataset, checkpoint, or approval status changed.

## 8. Download + extraction (executed)

- Integrity **PASS**: size `13264172619` bytes; MD5 `b62bd51d2ffcfaa76c60f234f0cc2bb3` (matches).
- The outer archive is a **zip of nested country zips** (Windows `tar` fails → "Damaged Zip archive"; extracted with Python `zipfile` instead).
- Extracted (inside `data\raw\RDD2022\RDD2022\`): China_Drone, China_MotorBike, Czech, India, Japan, United_States. **Norway (10.1 GB, drone) was NOT extracted** — out-of-domain for street-level pothole/crack; documented exclusion.

## 9. Annotation audit (READ-ONLY — measured)

Tool: `scripts/audit/phase20_rdd2022_audit.py` → `reports/phase20/rdd2022_audit.json`.

| Country | train imgs | train XMLs | paired | test imgs (unlabelled) |
|---|---|---|---|---|
| China_Drone | 2401 | 2401 | 2401 | 0 |
| China_MotorBike | 1977 | 1977 | 1977 | 500 |
| Czech | 2829 | 2829 | 2829 | 709 |
| India | 7706 | 7706 | 7706 | 1959 |
| Japan | 10506 | 10506 | 10506 | 2627 |
| United_States | 4805 | 4805 | 4805 | 1200 |
| **Total** | **30224** | **30224** | **30224** | **6995** |

- **Pairing:** perfect (0 images without XML, 0 XMLs without image).
- **Malformed:** 1 `zero_area` box (India). No parse errors.
- **Format:** Pascal VOC XML.
- **Class counts (raw):** D00 17446, D10 10100, D20 10149, D40 6083, plus
  **unexpected extra labels**: D01 179, D11 45, D0w0 1, D43 793, D44 5057,
  D50 3581, "Repair" 1046, "Block crack" 3.
- **Mapped to project (strict 4→2):** crack 37695, pothole 6083.
- **Excluded (NOT relabelled):** D01, D11, D0w0, D43, D44, D50, Repair, Block crack.
- **Duplicate filename stems:** 0.
- **Session leakage:** RDD2022 filenames are renumbered sequentially
  (`Country_000000.jpg`) with **no time/session metadata**, so filename-based
  session grouping is **not possible**. Leakage control relies on content-based
  duplicate grouping (see §10).

## 10. Duplicate / leakage scan (READ-ONLY — measured)

Tool: `scripts/audit/phase20_duplicate_scan.py` → `reports/phase20/duplicate_scan.json`.

- Indexed: **30,224** train images.
- **Exact duplicate groups: 1** (2 images).
- **Content (near-dup, dHash hamming ≤ 6) groups: 920** containing **4,266 images**
  (out of 26,878 total content groups).
- Largest near-dup groups are in China_Drone / China_MotorBike (texturally
  similar) and India. Splits MUST keep each group wholly in one split (Rule 15).
- **Limitation (disclosed):** near-dup grouping is content-based; images from the
  same physical location that are visually distinct cannot be grouped because
  capture/session metadata is absent. Residual leakage risk is documented.





