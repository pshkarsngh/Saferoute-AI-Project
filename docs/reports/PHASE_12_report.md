# PHASE_12 — Deterministic Risk Engine Report

===========================================
**Date (actual):** 2026-10-13  
**Engine version:** `risk-v1`  
**Model identifier:** `saferoute-yolo11-v1`  
**Phase ID:** PHASE_12  
**Governing Documents:** TRD §9, ARCHITECTURE §7, master_rules.md Rules 7, 9, 11, 12, 14, 17  

---

## 1. Formulas (Documented)

- **Hazard Density ($H_i$):**
  $$H_i = \frac{\sum_{k} \text{severity}_k}{\max(L_i / 1000.0, 0.10)}$$
  Where $L_i$ is segment length in meters. Normalised to hazard severity load per kilometre of road, with a minimum normalization floor of $0.10\text{ km}$ ($100\text{ m}$) to prevent division by near-zero segment lengths.
- **Exponential Decay Factor ($\lambda$):**
  $$\lambda = 0.10$$
  *Engineering Rationale:* $\lambda = 0.10$ provides a smooth, gradual decay curve where a moderate hazard density (e.g. $H_i = 10$, equivalent to roughly 3 potholes per km) yields $S_i \approx 36.8$, and high hazard densities ($H_i \ge 50$) decay toward zero ($S_i < 1.0$), while zero hazard yields a perfect score of $100.0$.
- **Segment Safety Score ($S_i$):**
  $$S_i = \text{clamp}\left(100.0 \times \exp(-\lambda \times H_i), 0.0, 100.0\right)$$
  Pure, non-negative, monotonically decreasing in $[0.0, 100.0]$.
- **Route Aggregation:**
  $$S_{\text{route}} = \frac{\sum_{i \in \text{assessed}} L_i \times S_i}{\sum_{i \in \text{assessed}} L_i}$$
  Length-weighted average across all assessed route segments. Unassessed segments are omitted from the numerical calculation and explicitly disclosed in limitations.

---

## 2. Coverage Rules (Rule 9)

- **Missing Imagery:**
  - Segments with 0 available images receive `segment_score: None`, `hazard_density_H: None`, `status: unassessed`, `is_suppressed: True`.
  - Missing imagery is **never** treated as zero risk or safe.
- **Insufficient Coverage (< 50%):**
  - If coverage fraction is $< 0.50$, the computed score has `is_suppressed: True` and an explicit limitation is added (`Insufficient imagery coverage (< 50%); safe verdict is suppressed`).
- **Route-level Propagation:**
  - If all segments lack imagery: `route_score: None`, `status: unassessed`.
  - If some segments lack imagery: `route_score` is computed over assessed segments only, with `status: partially_assessed` and limitation logged disclosing the unassessed fraction.

---

## 3. De-duplication Policy

- Within-image de-duplication handled by `HazardAggregator` using bounding box $\text{IoU} \ge 0.45$ and confidence tie-breaking.
- Route boundary de-duplication parameter configured in `config/risk_engine.yaml` (`dedup_adjacent_segments: true`, `adjacent_boundary_iou: 0.50`).

---

## 4. Configuration & Hash Traceability (Rule 17)

- **Configuration File:** [`config/risk_engine.yaml`](../../config/risk_engine.yaml)
- **Engine Config SHA-256 Hash:** `724905EB34E8CA2B20A3E75E948387500B4DF62C86E7DC9CE221985049635863`
- The exact hash is emitted with every `RouteSafetyResult` to guarantee complete reproducibility and auditability.

---

## 5. Output Contract

Strictly matching ARCHITECTURE §7 and TRD §9.1:
```json
{
  "route_id": "route_ab",
  "model_version": "saferoute-yolo11-v1",
  "route_score": 49.43,
  "coverage": {
    "images_total": 10,
    "images_used": 10,
    "fraction": 1.0
  },
  "config_hash": "724905EB34E8CA2B20A3E75E948387500B4DF62C86E7DC9CE221985049635863",
  "status": "assessed",
  "segments_count": 2,
  "segment_scores": [
    {
      "segment_id": "seg_a",
      "model_version": "saferoute-yolo11-v1",
      "length_m": 200.0,
      "coverage": {"images_total": 5, "images_used": 5, "fraction": 1.0},
      "hazard_density_H": 0.0,
      "segment_score": 100.0,
      "status": "assessed",
      "is_suppressed": false,
      "limitations": []
    },
    {
      "segment_id": "seg_b",
      "model_version": "saferoute-yolo11-v1",
      "length_m": 800.0,
      "coverage": {"images_total": 5, "images_used": 5, "fraction": 1.0},
      "hazard_density_H": 10.0,
      "segment_score": 36.79,
      "status": "assessed",
      "is_suppressed": false,
      "limitations": []
    }
  ],
  "limitations": []
}
```

---

## 6. Test Results (Empirical & Reproducible)

- **Determinism:** `test_pure_function_determinism` passed. Repeated evaluations yield identical scores, hashes, and schemas.
- **Empty vs Unassessed:** `test_candidate_formula_zero_hazard_is_perfect` verifies assessed 0-hazard gives 100.0, while `test_rule_9_missing_imagery_is_never_zero_risk` verifies missing imagery yields `None` score and `is_suppressed = True`.
- **Failed Handling:** `test_rule_9_failed_imagery_handling` passed; failed decode/imagery yields `None` score and `status = failed`.
- **Coverage Suppression:** `test_rule_9_insufficient_coverage_suppresses_safe_verdict` passed; coverage $< 50\%$ sets `is_suppressed = True`.
- **Boundary Cases:** Monotonic decay verified across $H \in [0, 200]$; minimum length clamp verified at $L = 50\text{ m}$.
- **Route Aggregation:** Length-weighted aggregation verified across mixed segments.
- **Separation of Concerns:** Zero LLM and zero facility data confirmed in schemas (`test_schema_serialization_and_isolation`).
- **Command:** `.\.venv\Scripts\python.exe -m unittest discover -s tests\unit -p "test_*.py" -v`
- **Passed / Total:** **42 / 42 passed (100%)** (including 12 dedicated `test_risk_engine.py` unit tests).

---

## 7. Validation Checklist

| # | Check | Status | Empirical Evidence |
|---|---|:---:|---|
| V1 | Sole ownership | PASS | `DeterministicRiskEngine` is the sole score calculator in `src.risk`. No detector or LLM produces safety scores. |
| V2 | Determinism | PASS | Verified in `test_pure_function_determinism`; identical inputs yield byte-identical outputs. |
| V3 | Documented formulas | PASS | Documented in `config/risk_engine.yaml`, `src/risk/README.md`, and this report. |
| V4 | Coverage honesty | PASS | Verified in `test_rule_9_missing_imagery_is_never_zero_risk` and `test_rule_9_insufficient_coverage_suppresses_safe_verdict`. |
| V5 | Failure handling | PASS | Verified in `test_rule_9_failed_imagery_handling`. |
| V6 | Separation | PASS | Verified in `test_schema_serialization_and_isolation`; zero facility counts, zero LLM calls. |
| V7 | Config hash | PASS | Emits 64-char uppercase SHA-256 hex string; verified in `test_config_hash_emission`. |
| V8 | Tests pass | PASS | 42/42 tests pass with exit code 0. |

---

## 8. Limitations & Honesty Note

1. **Candidate Formula:** The exponential decay model $S_i = 100 \times \exp(-\lambda H_i)$ is a deterministic candidate scoring formula. It represents mathematical severity load per kilometre, not an absolute guarantee of real-world vehicular safety.
2. **Mandatory Disclosures:** Safety scores must **always** be displayed alongside coverage percentage, assessment status, and any active suppressions.
3. **No Facilities in Score:** Facility data (lighting, hospitals, police stations) is handled separately in downstream integration and never mixed into the road surface hazard score.

---

## 9. Result & Next Phase

- **Result:** **COMPLETE**
- **Next Phase:** **PHASE_13 — Routing Provider Selection & Adapter**
- **Status:** Awaiting user authorization to proceed to Phase 13.
