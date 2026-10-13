"""SafeRoute AI — Deterministic Hazard Severity Policy.

Phase ID: PHASE_11
Policy Version: severity-v1
Follows: TRD §8.2, ARCHITECTURE §7, master_rules.md Rules 5, 7, 12.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml

DEFAULT_POLICY_PATH = Path("config/hazard_severity.yaml")


class SeverityPolicy:
    """Config-driven, deterministic severity assignment engine.
    
    Hard constraints:
    - Never uses an LLM to decide severity (Rule 7, Rule 12).
    - Every severity score is fully explainable from config + detection attributes.
    - Clamped strictly within documented [min_severity, max_severity] bounds.
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None, config_dict: Optional[Dict[str, Any]] = None):
        if config_dict is not None:
            self.config = config_dict
        else:
            if config_path is None:
                workspace_root = Path(__file__).resolve().parent.parent.parent
                config_path = workspace_root / DEFAULT_POLICY_PATH
            else:
                config_path = Path(config_path)

            if not config_path.is_file():
                raise FileNotFoundError(f"Severity configuration not found at {config_path}")

            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)

        self.version = self.config.get("metadata", {}).get("policy_version", "severity-v1")
        self.model_version = self.config.get("metadata", {}).get("model_version", "saferoute-yolo11-v1")

        # Thresholds
        t_cfg = self.config.get("thresholds", {})
        self.confidence_threshold = float(t_cfg.get("confidence_threshold", 0.25))
        self.dedup_iou_threshold = float(t_cfg.get("dedup_iou_threshold", 0.45))
        self.min_area = float(t_cfg.get("min_bbox_area_norm", 0.0001))
        self.max_area = float(t_cfg.get("max_bbox_area_norm", 0.30))

        # Base severities
        self.base_severities = {k.lower(): float(v) for k, v in self.config.get("base_severities", {}).items()}

        # Modulation parameters
        m_cfg = self.config.get("modulation", {})
        self.modulation_enabled = bool(m_cfg.get("enabled", True))
        self.alpha_conf = float(m_cfg.get("alpha_confidence", 0.25))
        self.beta_area = float(m_cfg.get("beta_area", 0.50))
        self.min_severity = float(m_cfg.get("min_severity", 1.0))
        self.max_severity = float(m_cfg.get("max_severity", 5.0))

    def get_base_severity(self, hazard_class: str) -> float:
        """Retrieve base severity for a hazard class."""
        key = hazard_class.lower()
        if key in self.base_severities:
            return self.base_severities[key]
        return self.base_severities.get("unsupported", 1.0)

    def compute_bbox_area_norm(self, bbox_norm: List[float]) -> float:
        """Compute normalized 2D bounding box area from [nx1, ny1, nx2, ny2]."""
        if len(bbox_norm) < 4:
            return 0.0
        w = max(0.0, bbox_norm[2] - bbox_norm[0])
        h = max(0.0, bbox_norm[3] - bbox_norm[1])
        return float(w * h)

    def calculate_severity(
        self,
        hazard_class: str,
        confidence: float,
        bbox_norm: List[float],
    ) -> float:
        """Compute bounded, deterministic severity from detection attributes.
        
        Formula:
            area_norm = clamp(area, 0, max_area)
            area_factor = 1.0 + beta_area * (area_norm / max_area)
            conf_factor = 1.0 + alpha_conf * (confidence - conf_thresh)
            severity = clamp(base_severity * area_factor * conf_factor, min_severity, max_severity)
        """
        base_sev = self.get_base_severity(hazard_class)

        if not self.modulation_enabled:
            return float(max(self.min_severity, min(self.max_severity, base_sev)))

        # 1. Area factor
        raw_area = self.compute_bbox_area_norm(bbox_norm)
        clamped_area = max(0.0, min(self.max_area, raw_area))
        area_ratio = clamped_area / max(1e-6, self.max_area)
        area_factor = 1.0 + (self.beta_area * area_ratio)

        # 2. Confidence factor
        conf_clamped = max(0.0, min(1.0, float(confidence)))
        conf_delta = conf_clamped - self.confidence_threshold
        conf_factor = 1.0 + (self.alpha_conf * conf_delta)

        # 3. Modulated severity
        raw_severity = base_sev * area_factor * conf_factor
        bounded_severity = max(self.min_severity, min(self.max_severity, raw_severity))
        return round(float(bounded_severity), 2)

    def explain_severity(
        self,
        hazard_class: str,
        confidence: float,
        bbox_norm: List[float],
    ) -> Dict[str, Any]:
        """Explain the exact numeric derivation of a severity assignment."""
        base_sev = self.get_base_severity(hazard_class)
        raw_area = self.compute_bbox_area_norm(bbox_norm)
        clamped_area = max(0.0, min(self.max_area, raw_area))
        area_factor = 1.0 + (self.beta_area * (clamped_area / self.max_area))
        conf_factor = 1.0 + (self.alpha_conf * (confidence - self.confidence_threshold))
        final_severity = self.calculate_severity(hazard_class, confidence, bbox_norm)

        return {
            "policy_version": self.version,
            "hazard_class": hazard_class,
            "base_severity": base_sev,
            "confidence": round(float(confidence), 4),
            "confidence_threshold": self.confidence_threshold,
            "confidence_factor": round(float(conf_factor), 4),
            "normalized_area": round(float(raw_area), 6),
            "area_factor": round(float(area_factor), 4),
            "final_severity": final_severity,
            "bounds": [self.min_severity, self.max_severity],
        }
