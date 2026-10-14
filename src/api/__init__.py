"""SafeRoute AI — Backend API package (PHASE_16).

Stdlib HTTP API + SQLite persistence orchestrating the full pipeline:
routing -> imagery -> preprocessing -> detection -> aggregation -> risk -> comparison.
"""

from src.api.pipeline import SafetyAnalysisPipeline
from src.api.store import AnalysisStore
from src.api.bootstrap import build_pipeline, build_geocoder

__version__ = "api-v1"

__all__ = ["SafetyAnalysisPipeline", "AnalysisStore", "build_pipeline", "build_geocoder"]
