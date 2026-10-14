"""SafeRoute AI — Geocoding domain contracts.

Turns a human place name ("MG Road, Bangalore") into coordinates so real users
never have to type latitude/longitude. Provider-independent (TRD §10 style).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class GeocodeStatus(str, Enum):
    """Categorical outcome of a geocoding request."""

    OK = "ok"
    NO_RESULTS = "no_results"
    INVALID_REQUEST = "invalid_request"
    PROVIDER_ERROR = "provider_error"
    PROVIDER_TIMEOUT = "provider_timeout"
    RATE_LIMITED = "rate_limited"
    DISABLED = "disabled"


@dataclass(frozen=True)
class GeocodeCandidate:
    """A single resolved place with geographic coordinates."""

    display_name: str
    latitude: float
    longitude: float
    provider: str
    importance: Optional[float] = None
    bbox: Optional[Tuple[float, float, float, float]] = None  # (south, north, west, east)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "display_name": self.display_name,
            "latitude": round(float(self.latitude), 6),
            "longitude": round(float(self.longitude), 6),
            "provider": self.provider,
            "importance": round(float(self.importance), 4) if self.importance is not None else None,
            "bbox": list(self.bbox) if self.bbox else None,
        }


@dataclass
class GeocodeResult:
    """Standardized geocoding response (provenance always recorded)."""

    status: GeocodeStatus
    provider: str
    query: str
    candidates: List[GeocodeCandidate] = field(default_factory=list)
    retrieved_at: str = ""
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "provider": self.provider,
            "query": self.query,
            "candidates_count": len(self.candidates),
            "candidates": [c.to_dict() for c in self.candidates],
            "retrieved_at": self.retrieved_at,
            "error_message": self.error_message,
        }
