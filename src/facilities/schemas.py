"""SafeRoute AI — Facilities Domain Data Contracts & Schemas.

Phase ID: PHASE_15
Follows PRD §4.7, TRD §4.7, ARCHITECTURE §8, master_rules.md Rules 11, 13, 20.

Facilities are presentation/context only. These schemas deliberately contain
NO score, risk or hazard fields: facilities must never enter the hazard score
or route ranking (Rule 11).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FacilityStatus(str, Enum):
    """Categorical outcome of a facilities lookup."""
    OK = "ok"
    UNAVAILABLE = "unavailable"          # No data / none found (honest, not fabricated)
    PROVIDER_ERROR = "provider_error"
    PROVIDER_TIMEOUT = "provider_timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_REQUEST = "invalid_request"


@dataclass(frozen=True)
class Facility:
    """A single nearby facility. Context only — never a safety input (Rule 11)."""
    facility_id: str
    category: str
    name: str
    latitude: float
    longitude: float
    distance_m: float
    source: str
    status: str = "ok"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facility_id": self.facility_id,
            "category": self.category,
            "name": self.name,
            "latitude": round(float(self.latitude), 6),
            "longitude": round(float(self.longitude), 6),
            "distance_m": round(float(self.distance_m), 1),
            "source": self.source,
            "status": self.status,
        }


@dataclass
class FacilityResult:
    """Standardized facilities lookup response.

    Provenance (provider, timestamp, radius, categories) is always recorded so
    every facility claim is auditable (Rule 17, Rule 20). Absence of facilities
    is reported as an explicit status, never invented (Rule 20).
    """
    status: FacilityStatus
    provider: str
    facilities: List[Facility] = field(default_factory=list)
    categories_requested: List[str] = field(default_factory=list)
    radius_m: float = 0.0
    origin_latitude: float = 0.0
    origin_longitude: float = 0.0
    retrieved_at: str = ""
    limitations: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "provider": self.provider,
            "facilities_count": len(self.facilities),
            "facilities": [f.to_dict() for f in self.facilities],
            "categories_requested": list(self.categories_requested),
            "radius_m": round(float(self.radius_m), 1),
            "origin": {
                "latitude": round(float(self.origin_latitude), 6),
                "longitude": round(float(self.origin_longitude), 6),
            },
            "retrieved_at": self.retrieved_at,
            "limitations": list(self.limitations),
            "error_message": self.error_message,
        }
