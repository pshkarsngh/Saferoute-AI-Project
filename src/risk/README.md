# SafeRoute AI — Hazard Aggregation & Deterministic Risk Engine (`src.risk`)

> **Policy Version:** `severity-v1`  
> **Engine Version:** `risk-v1`  
> **Model Identifier:** `saferoute-yolo11-v1`  
> **Phase IDs:** PHASE_11, PHASE_12  
> **Governing documents:** [`../../master_rules.md`](../../master_rules.md) (Rules 5, 7, 9, 11, 12, 14, 17), TRD §8-§9, ARCHITECTURE §7.

---

## 1. Overview

The `src.risk` package translates raw computer vision object detections into structured hazard records, computes segment-level hazard assessments, and deterministically calculates safety scores for segments and full routes.

### Invariants:
1. **Deterministic & Config-Driven (Rule 7, Rule 17):** All severity values, confidence filters, de-duplication thresholds, decay factors ($\lambda$), and coverage parameters are loaded directly from configuration files (`config/hazard_severity.yaml`, `config/risk_engine.yaml`). Output hashes are traceable.
2. **Sole Risk Engine Ownership (Rule 7):** The deterministic risk engine is the **sole** component authorized to compute safety scores.
3. **Zero LLM Involvement (Rule 12):** Neither severity aggregation nor safety scoring involves an LLM.
4. **Separation of Concerns (Rule 11):** Nearby facility counts (police, hospitals, lighting) are strictly excluded from road hazard safety scores.
5. **Missing Imagery is NOT Zero Risk (Rule 9):** Segments with missing, unretrieved, or corrupt road imagery are explicitly classified as `unassessed` or `partially_assessed`, never assumed clean or safe (score is `None`, suppressed).

---

## 2. Severity Policy Specification (`severity-v1`)

Configured in [`config/hazard_severity.yaml`](../../config/hazard_severity.yaml):

### Base Severity Table
| Hazard Class | Base Severity | Scale | Engineering Rationale |
|---|:---:|:---:|---|
| `pothole` | `3.0` | 1.0 – 5.0 | Direct tire puncture risk, suspension damage, sudden loss of vehicle control. |
| `crack` | `1.5` | 1.0 – 5.0 | Surface fissure; reduces wet tire adhesion, precursor to pothole formation. |
| `unsupported` | `1.0` | 1.0 – 5.0 | Fallback for uncalibrated/unsupported detections, explicitly disclosed. |

### Modulation Formula (Bounded in [1.0, 5.0])
Severity is dynamically modulated based on detection confidence and normalized image bounding area:

$$\text{area\_norm} = \text{clamp}(w_{\text{norm}} \times h_{\text{norm}}, 0, \text{max\_area})$$

$$\text{area\_factor} = 1.0 + \beta \times \left(\frac{\text{area\_norm}}{\text{max\_area}}\right)$$

$$\text{conf\_factor} = 1.0 + \alpha \times (\text{confidence} - \text{conf\_threshold})$$

$$\text{severity} = \text{clamp}(\text{base\_severity} \times \text{area\_factor} \times \text{conf\_factor}, \text{min\_severity}, \text{max\_severity})$$

*Default parameters:* $\alpha = 0.25$, $\beta = 0.50$, $\text{max\_area} = 0.30$, bounds: $[1.0, 5.0]$.

---

## 3. Confidence Thresholding & Spatial De-duplication

- **Confidence Threshold (`0.25`):** Detections with confidence $< 0.25$ are filtered out to eliminate spurious background noise.
- **IoU De-duplication (`0.45`):** When multiple overlapping bounding boxes of the same class occur within an image:
  - If $\text{IoU} \ge 0.45$, the duplicate with the lower confidence is suppressed (tie-break rule).

---

## 4. Deterministic Risk Engine (`risk-v1`)

Configured in [`config/risk_engine.yaml`](../../config/risk_engine.yaml):

### 4.1 Hazard Density ($H_i$)
Normalized severity load per kilometer:
$$H_i = \frac{\sum_{k} \text{severity}_k}{\max(L_i / 1000.0, 0.10)}$$
where $L_i$ is segment length in meters (minimum baseline $0.10\text{ km} = 100\text{ m}$).

### 4.2 Candidate Segment Safety Score ($S_i$)
$$S_i = \text{clamp}\left(100.0 \times \exp(-\lambda \cdot H_i), 0.0, 100.0\right)$$
where $\lambda = 0.10$.
- Zero hazards ($H_i = 0$): $S_i = 100.0$.
- Non-negative, monotonic decay: As $H_i \to \infty$, $S_i \to 0.0$.

### 4.3 Route-Level Aggregation
Length-weighted combination of assessed segments:
$$S_{\text{route}} = \frac{\sum_{i \in \text{assessed}} L_i \cdot S_i}{\sum_{i \in \text{assessed}} L_i}$$

---

## 5. Segment Coverage & Status Propagation (Rule 9)

| Status | Condition | Handling |
|---|---|---|
| `assessed` | 100% of expected images processed, coverage $\ge 90\%$. | Unsuppressed deterministic safety score. |
| `partially_assessed` | Images processed $> 0$, coverage $< 90\%$. | Missing segments omitted from weighted score; limitation logged. If coverage $< 50\%$, safe verdict suppressed. |
| `unassessed` | 0 images available for segment / route. | Missing imagery explicitly flagged; **score is `None`**, never assumed zero risk. |
| `failed` | All imagery failed validation/decoding. | Pipeline failure logged; **score is `None`**. |

---

## 6. Usage Example

```python
from src.risk import (
    HazardAggregator,
    SeverityPolicy,
    DeterministicRiskEngine,
)

# 1. Initialize policy, aggregator, and deterministic engine
policy = SeverityPolicy()
aggregator = HazardAggregator(policy)
engine = DeterministicRiskEngine()

# 2. Aggregate image detections into a segment assessment
assessment = aggregator.assess_segment(
    segment_id="seg_001",
    image_results=[image_result_1, image_result_2],
    expected_image_count=2,
    route_id="route_north",
)

# 3. Score a segment
segment_score = engine.score_segment(assessment, length_m=500.0)
print(f"Segment score: {segment_score.segment_score}/100, Density H: {segment_score.hazard_density_H}")

# 4. Score a full route
route_score = engine.score_route(
    route_id="route_north",
    segment_assessments=[assessment],
    segment_lengths_m=[500.0],
)
print(f"Route score: {route_score.route_score}/100, Hash: {route_score.config_hash[:8]}...")
```
