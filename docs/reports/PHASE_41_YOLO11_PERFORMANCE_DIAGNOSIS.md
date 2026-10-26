# PHASE 41 — YOLO11 Performance Diagnosis

> **Status:** Completed  
> **Date:** 2026-10-26  
> **Branch/HEAD:** `main` @ `44f0cbf`  
> **Checkpoint:** `models/training/saferoute-yolo11-v2/weights/best.pt`  
> **Dataset:** `data/datayolo_prep/` (same-source scene-grouped held-out test)

## 1) Per-class metrics (actual)
From Ultralytics evaluation on test split (269 images, 405 instances):

| Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|
| all | 269 | 405 | 0.114 | 0.094 | 0.0423 | 0.0121 |
| pothole | 148 | 250 | 0.164 | 0.136 | 0.070 | 0.0211 |
| crack | 129 | 155 | 0.064 | 0.052 | 0.015 | 0.0031 |

**Finding:** Potholes perform better than cracks (recall/precision higher), but both are very low. Cracks are the weaker class.

## 2) Dataset/label inspection
- **Format:** YOLO normalized xywh, 2 classes (0=pothole, 1=crack) ✓
- **Test:** 269 images, 269 label files, 405 boxes total ✓
- **dataset.yaml:** Test is marked as same-source scene-grouped held-out (not independent benchmark) ✓
- **Original split audit:** Shows original DATA-YOLO test split was unlabelled (`unlabelled_test_split`); current test set is a prepared held-out set from data/datayolo_prep
- **Label/image pairing:** Present for all test images
- **Class distribution:** Pothole 250 instances (62%), crack 155 (38%) - imbalanced

## 3) Training/metadata
- **Checkpoint:** saferoute-yolo11-v2/best.pt (v2 promoted per Phase 24G)
- **Config:** imgsz 640, conf 0.25, iou 0.45 (inference config matches)
- **Architecture:** YOLO11 (Ultralytics)
- **Training history:** Not fully visible in repo; only weights present. No detailed loss curves inspected.
- **Classes:** 2 classes only (matches supported set)

## 4) Runtime vs evaluation settings
- **Evaluation:** imgsz=640, device=GPU, verbose=False (default Ultralytics settings)
- **Runtime:** imgsz=640, conf=0.25, iou=0.45, device=auto/GPU - consistent
- **Preprocessing:** Both use letterbox/standard preprocessing

## 5) Root causes (ranked by evidence)
1. **Same-source/domain shift / limited generalization** (HIGH) - Test set is same-source scene-grouped held-out per dataset.yaml; low metrics suggest overfitting to training distribution or dataset characteristics
2. **Class imbalance & difficulty** (HIGH) - Cracks harder to detect (0.064 precision) vs potholes (0.164); fewer crack instances
3. **Small dataset / annotation quality** (MEDIUM) - 269 test images may be limited; annotation consistency not fully verified
4. **Model capacity/training** (MEDIUM) - Without training logs hard to assess; but v2 was promoted as improvement
5. **Inference settings** (LOW) - Settings consistent, not the primary cause

## 6) Recommended corrective actions (priority order)
**Do NOT implement without authorization:**
1. **Get independent test set** - Most critical. Current test is same-source; need truly independent labeled test set for valid accuracy measurement
2. **Analyze errors** - Inspect FP/FN samples to understand failure modes (localization vs classification)
3. **Review annotations** - Check label quality, especially for cracks
4. **Consider data augmentation/training** - Only if independent validation confirms issues
5. **Tune confidence** - Test different thresholds, but must maintain policy consistency

## 7) Independent evaluation set needed?
**YES.** The dataset.yaml explicitly states test is "same-source scene-grouped held-out list, NOT an independent benchmark. Do not report it as a trustworthy generalisation metric." A valid independent evaluation requires:
- Different source/location/time than training data
- Properly labeled ground truth
- Representative of deployment conditions
- No scene overlap with training

## Conclusion
Low accuracy is consistent with same-source test set limitations. Potholes perform better than cracks. **No fixes implemented.** Requires authorization for any model/data changes. Independent test set is needed for reliable accuracy assessment.

**Files inspected:** `runs/detect/val*/` results, dataset manifests, original_split_audit.csv, config/detection.yaml  
**No code/model changes made.**
