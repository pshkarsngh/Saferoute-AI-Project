"""SafeRoute AI — LLM Explanation output schema (PHASE_17)."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ExplanationResult:
    """Schema-validated, grounded explanation of verified backend results.

    `source` is "ollama" or "fallback". The explanation is derived ONLY from
    verified data; referenced entities must exist in the input (Rule 12).
    """
    analysis_id: str
    explanation: str
    referenced_routes: List[str] = field(default_factory=list)
    referenced_hazards: List[str] = field(default_factory=list)
    disclosures: List[str] = field(default_factory=list)
    source: str = "fallback"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "explanation": self.explanation,
            "referenced_routes": list(self.referenced_routes),
            "referenced_hazards": list(self.referenced_hazards),
            "disclosures": list(self.disclosures),
            "source": self.source,
        }
