# PHASE_11 — Hazard Aggregation & Severity Report

> **Phase ID:** PHASE_11  
> **Status:** COMPLETE  
> **Date (actual):** 2026-10-13  
> **Workspace:** `D:\New folder (3)`  
> **Policy Version:** `severity-v1`  
> **Model Identifier:** `saferoute-yolo11-v1`  
> **Predecessor:** [`PHASE_10`](./PHASE_10_report.md) — Inference & Structured Detection Pipeline  
> **Successor:** [`PHASE_12`](../phases/PHASE_12.md) — Deterministic Risk Engine  
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) · [`../TRD.md`](../TRD.md) · [`../ARCHITECTURE.md`](../ARCHITECTURE.md) · [`../phases/PHASE_11.md`](../phases/PHASE_11.md)  
> **Approval Reference:** User explicit directive `next` (2026-10-13)

---

## 1. Severity Policy (`config/hazard_severity.yaml`)

Severity is assigned strictly through a deterministic, config-driven lookup and bounded modulation formula without LLM involvement (Rule 7, Rule 12):

### Base Severity Assignments
| Hazard Class | Base Severity | Scale | Engineering Rationale |
|---|:---:|:---:|---|
| `pothole` | `3.0` | 1.0 – 5.0 | Mechanical shock hazard, sudden loss of vehicle control, risk of blowout/rim fracture. |
| `crack` | `1.5` | 1.0 – 5.0 | Surface fissure; reduces wet tire adhesion, precursor to structural pothole decay. |
| `unsupported` | `1.0` | 1.0 – 5.0 | Fallback for uncalibrated/unsupported detections, explicitly disclosed. |

### Dynamic Modulation Formula
$$\text{area\_norm} = \text{clamp}(w_{\text{norm}} \times h_{\text{norm}}, 0, \text{max\_area})$$
$$\text{area\_factor} = 1.0 + \beta \times \left(\frac{\text{area\_norm}}{\text{max\_area}}\right)$$
$$\text{conf\_factor} = 1.0 + \alpha \times (\text{confidence} - \text{conf\_threshold})$$
$$\text{severity} = \text{clamp}(\text{base\_severity} \times \text{area\_factor} \times \text{conf\_factor}, \text{min\_severity}, \text{max\_severity})$$

- **Parameters:** $\alpha = 0.25$, $\beta = 0.50$, $\text{max\_area} = 0.30$, clamped strictly to $[1.0, 5.0]$.
- **Explainability:** Fully traceable via `SeverityPolicy.explain_severity()`.

---

## 2. Confidence Threshold

- **Value:** `0.25`
- **Location:** `config/hazard_severity.yaml` (`thresholds.confidence_threshold`)
- **Validation Evidence:** Calibrated during Phase 09 evaluation. Detections below 0.25 on held-out test data exhibited high background false positive rates (tar seams, roadside shadows). Filtering at 0.25 eliminates noise while preserving true road hazard boundaries.

---

## 3. De-duplication Rule (TRD §8.3)

- **Method:** Spatial Bounding Box Intersection-over-Union (IoU) Non-Maximum Suppression beyond detector NMS.
- **IoU Overlap Threshold:** `0.45` (`thresholds.dedup_iou_threshold`)
- **Tie-Break Rule:** When multiple candidate detections of the same hazard class have $\text{IoU} \ge 0.45$, the candidate with the higher detection confidence score is retained; lower-confidence duplicates are suppressed.

---

## 4. Hazard Record Contract (TRD §8.1)

Outputs conform to the JSON-serializable `HazardRecord` specification:

```json
{
  "model_version": "saferoute-yolo11-v1",
  "image_id": "img-001",
  "route_id": "route-1",
  "segment_id": "seg-1-0",
  "hazard_class": "pothole",
  "confidence": 0.75,
  "bbox_xyxy": [50.0, 60.0, 150.0, 180.0],
  "bbox_norm": [0.0781, 0.1667, 0.2344, 0.5],
  "severity": 3.42,
  "status": "assessed",
  "error": null
}
```

---

## 5. Status Handling & Rule 9 Missing Imagery Rule

Segment assessments categorize coverage and diagnostic status explicitly:

| Status | Trigger Condition | Handling & Disclosures |
|---|---|---|
| **`assessed`** | 100% of expected images processed successfully, 0 failed. | Confirmed hazard tally for segment. |
| **`partially_assessed`** | Coverage fraction $> 0$ but $< 1.0$, or some images failed. | Uncovered sections flagged as unassessed in `limitations`. |
| **`unassessed`** | 0 images available for segment. | **Rule 9 strictly enforced: Missing imagery is NEVER zero risk.** Segment is marked unassessed. |
| **`failed`** | All images failed validation or decoding. | Disclosed as processing failure. |

---

## 6. Test Results (Actual)

Executed via `.\.venv\Scripts\python.exe -m unittest discover -s tests\unit -p "test_*.py" -v`:

- **Phase 11 Suite (`tests/unit/test_hazard_aggregation.py`):**
  - `test_policy_loading_and_base_severities` ... **ok**
  - `test_severity_calculation_and_bounding` ... **ok**
  - `test_severity_explanation_traceability` ... **ok**
  - `test_iou_calculation` ... **ok**
  - `test_confidence_threshold_filtering` ... **ok**
  - `test_iou_deduplication_tie_break` ... **ok**
  - `test_hazard_record_contract_schema` ... **ok**
  - `test_status_propagation_full_assessed` ... **ok**
  - `test_status_propagation_missing_imagery_rule9` ... **ok**
  - `test_status_propagation_partial_coverage` ... **ok**
  - `test_status_propagation_failed_imagery` ... **ok**
  - `test_rule7_and_12_no_safety_scores_computed` ... **ok**
- **Test Summary:** **12 / 12 Phase 11 tests passed** (30 / 30 total tests passing across workspace).

---

## 7. Validation Results Summary

| # | Check | Pass Condition | Status | Evidence |
|---|---|---|:---:|---|
| **V1** | Policy config-driven | Severity comes solely from YAML config | **PASS** | `config/hazard_severity.yaml` |
| **V2** | Explainable | Traceable to config + detection attributes | **PASS** | Verified via `explain_severity()` |
| **V3** | Threshold validated | Value validated and documented | **PASS** | `0.25` calibrated from Phase 09 |
| **V4** | De-dup documented | IoU overlap rule with tie-break | **PASS** | IoU threshold `0.45` tested |
| **V5** | Contract conforms | Matches TRD §8.1 | **PASS** | `HazardRecord.to_dict()` verified |
| **V6** | Statuses complete | All 4 statuses handled and tested | **PASS** | Unit tests cover all 4 states |
| **V7** | Unknown stays unknown | Missing evidence -> unassessed (not zero risk) | **PASS** | Rule 9 enforced and verified |
| **V8** | No LLM, no score | No LLM used; no safety scores computed | **PASS** | Verified by unit tests |
| **V9** | Tests pass | Tests executed and passing | **PASS** | 12/12 passed (30/30 overall) |

---

## 8. Limitations & Honesty Note (TRD §8.2, Rules 7, 10, 20)

- **Provisional Policy:** This severity policy is a documented engineering model, not an actuarially calibrated road damage model.
- **No Safety Scores in Phase 11:** The aggregator computes total raw hazard load $H_i = \sum \text{severity}$; route safety scores ($S_i = 100 \cdot e^{-\lambda H_i}$) are exclusively computed by the deterministic risk engine in [PHASE_12](../phases/PHASE_12.md).

---

## 9. Result & Next Phase

- **Result:** **`COMPLETE`**
- **Next Phase Authorised?** **`NO`** — awaiting explicit user review and approval before starting [`PHASE_12`](../phases/PHASE_12.md) (Deterministic Risk Engine).
