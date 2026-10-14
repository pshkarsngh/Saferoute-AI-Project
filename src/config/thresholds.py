"""SafeRoute AI — single confidence-threshold policy (PHASE_22, Rule 7/9).

The detector (`config/detection.yaml` -> inference.conf) and the aggregator
(`config/hazard_severity.yaml` -> thresholds.confidence_threshold) MUST agree.
If the detector runs LOWER than the aggregator, detections in the gap are
silently discarded — which previously produced "zero hazards -> score 100".

This module is the single source of truth and fails loudly (never silently) if
the two configured values diverge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DETECTION_REL = Path("config/detection.yaml")
SEVERITY_REL = Path("config/hazard_severity.yaml")


@dataclass(frozen=True)
class ThresholdPolicy:
    detector_conf: float
    aggregator_conf: float

    @property
    def consistent(self) -> bool:
        return abs(self.detector_conf - self.aggregator_conf) < 1e-9

    @property
    def value(self) -> float:
        return self.aggregator_conf


def _read(path: Path) -> dict:
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_threshold_policy(
    detection_config: Optional[Union[str, Path]] = None,
    severity_config: Optional[Union[str, Path]] = None,
) -> ThresholdPolicy:
    det_path = Path(detection_config) if detection_config else (WORKSPACE_ROOT / DETECTION_REL)
    sev_path = Path(severity_config) if severity_config else (WORKSPACE_ROOT / SEVERITY_REL)
    det = _read(det_path).get("inference", {}).get("conf", 0.25)
    sev = _read(sev_path).get("thresholds", {}).get("confidence_threshold", 0.25)
    return ThresholdPolicy(detector_conf=float(det), aggregator_conf=float(sev))


def assert_threshold_consistency(
    detection_config: Optional[Union[str, Path]] = None,
    severity_config: Optional[Union[str, Path]] = None,
) -> ThresholdPolicy:
    """Return the policy or raise if detector and aggregator thresholds differ."""
    policy = load_threshold_policy(detection_config, severity_config)
    if not policy.consistent:
        raise ValueError(
            "Inconsistent confidence thresholds: detector conf="
            f"{policy.detector_conf} != aggregator confidence_threshold="
            f"{policy.aggregator_conf}. Detections in the gap would be silently "
            "discarded (PHASE_22). Align config/detection.yaml and "
            "config/hazard_severity.yaml."
        )
    return policy
