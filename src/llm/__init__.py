"""SafeRoute AI — Grounded LLM Explanation Layer (PHASE_17).

The LLM explains verified backend data only. It never computes or alters scores
(Rules 7, 12) and never invents routes, hazards, facilities, or measurements.

Package exports:
    ExplanationResult
    GroundedExplanationService
"""

from src.llm.schemas import ExplanationResult
from src.llm.explainer import GroundedExplanationService

__version__ = "llm-v1"

__all__ = ["ExplanationResult", "GroundedExplanationService"]
