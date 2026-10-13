# SafeRoute AI — Model Evaluation & Acceptance Plan
# Phase ID: PHASE_07 (Frozen Evaluation Plan for PHASE_09)
# Follows TRD §6, TRAINING_RULES.md §5, master_rules.md Rules 14, 15

## 1. Objective
Establish objective, non-fabricated quantitative evaluation criteria and qualitative checks for the baseline detector (`saferoute-yolo11-v1`).

---

## 2. Test Set Isolation Protocol
- **Strict Isolation:** The held-out test split (`data/splits/test.txt`, 201 images) remains **completely unread and untouched** during training and validation tuning.
- **Model Checkpoint Selection:** Checkpoint selection (`best.pt`) is governed strictly by the validation split (`data/splits/val.txt`, 402 images).
- **Single Evaluation Run:** Test evaluation runs exactly once after training completion in PHASE_09.

---

## 3. Quantitative Metrics Suite
All metrics must be recorded as measured by Ultralytics / PyTorch without manual modification or estimates:
1. **mAP@0.5:** Mean Average Precision at IoU threshold 0.50 (overall and per-class).
2. **mAP@0.5:0.95:** Mean Average Precision across IoU thresholds 0.50 to 0.95 in steps of 0.05.
3. **Precision (P):** Overall and per-class precision at optimal confidence threshold.
4. **Recall (R):** Overall and per-class recall at optimal confidence threshold.
5. **F1-Score:** Harmonic mean of precision and recall.
6. **Confusion Matrix:** Normalized and raw confusion matrix across background, `pothole`, and `crack`.

---

## 4. Per-Class Analysis & Error Categorization
- **Pothole Detection Evaluation:** Evaluate P, R, and mAP@0.5 specifically for class 0.
- **Crack Detection Evaluation:** Evaluate P, R, and mAP@0.5 specifically for class 1.
- **Background False Positives:** Review background false positive rate (e.g. shadows or road patches mistaken for hazards).
- **Missed Detection Analysis (False Negatives):** Inspect small or low-contrast cracks/potholes missed by the detector.
- **Unsupported Class Check:** Verify that class 2 (`manhole`) annotations are not erroneously generated or relabelled as potholes or cracks.

---

## 5. Qualitative Human Review Sample
- A sample of 20 images from the held-out test set (10 positive images, 10 negative/challenging images) will be rendered with bounding boxes via `src.preprocessing.visualise()` into `logs/evaluation/qualitative_samples/`.
- Reviewers inspect bounding box tightness, false triggers, and detection confidences.

---

## 6. Checkpoint Acceptance Gates (for PHASE_09)
To be considered for promotion:
- Model must train to completion and produce verifiable checkpoint weights (`best.pt`, `last.pt`).
- Validation loss curves must demonstrate convergence without severe catastrophic overfitting.
- Metrics must be reported honestly with raw log evidence.
