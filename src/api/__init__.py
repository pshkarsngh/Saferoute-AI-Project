"""SafeRoute AI — Backend API package (PHASE_16).

Stdlib HTTP API + SQLite persistence orchestrating the full pipeline:
routing -> imagery -> preprocessing -> detection -> aggregation -> risk -> comparison.
"""

from src.api.pipeline import SafetyAnalysisPipeline
from src.api.store import AnalysisStore

__version__ = "api-v1"

__all__ = ["SafetyAnalysisPipeline", "AnalysisStore"]
