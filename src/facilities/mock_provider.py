"""SafeRoute AI — Deterministic Mock Facilities Provider (PHASE_15).

Offline fixtures for tests/demo. No network. Facilities are context only
(Rule 11) and are always labelled with source="mock_facilities".
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.facilities.interfaces import FacilitiesProvider
from src.facilities.schemas import Facility, FacilityResult, FacilityStatus
from src.routing.segmentation import haversine_distance_m

# Offsets (in degrees) from the origin so a deterministic set of nearby
# facilities is produced for any origin. ~0.001 deg is ~111 m.
_FIXTURES: List[Dict] = [
    {"category": "hospital", "name": "City General Hospital", "dlat": 0.004, "dlon": 0.003},
    {"category": "pharmacy", "name": "Wellness Pharmacy", "dlat": 0.001, "dlon": -0.001},
    {"category": "police", "name": "Central Police Station", "dlat": -0.002, "dlon": 0.002},
    {"category": "fuel", "name": "Highway Fuel Pump", "dlat": 0.003, "dlon": -0.004},
    {"category": "hotel", "name": "Transit Hotel", "dlat": -0.003, "dlon": -0.002},
    {"category": "restaurant", "name": "Roadside Restaurant", "dlat": 0.002, "dlon": 0.005},
]


class MockFacilitiesProvider(FacilitiesProvider):
    """Deterministic offline facilities provider for reproducible tests/demo."""

    def __init__(self, available: bool = True, error_mode: Optional[str] = None):
        self.available = available
        self.error_mode = error_mode

    @property
    def provider_name(self) -> str:
        return "mock_facilities"

    def get_nearby_facilities(self, latitude, longitude, radius_m=None, categories=None):
        now = datetime.now(timezone.utc).isoformat()
        radius = float(radius_m if radius_m is not None else 1000.0)
        cats = list(categories) if categories else [f["category"] for f in _FIXTURES]

        base = dict(provider=self.provider_name, categories_requested=cats,
                    radius_m=radius, origin_latitude=latitude, origin_longitude=longitude,
                    retrieved_at=now)

        if self.error_mode == "timeout":
            return FacilityResult(status=FacilityStatus.PROVIDER_TIMEOUT,
                                  error_message="Mock provider timeout.", **base)
        if self.error_mode == "provider_error":
            return FacilityResult(status=FacilityStatus.PROVIDER_ERROR,
                                  error_message="Mock provider 5xx error.", **base)
        if self.error_mode == "rate_limited":
            return FacilityResult(status=FacilityStatus.RATE_LIMITED,
                                  error_message="Mock provider rate limited.", **base)

        results: List[Facility] = []
        for i, fx in enumerate(_FIXTURES):
            if fx["category"] not in cats:
                continue
            lat = latitude + fx["dlat"]
            lon = longitude + fx["dlon"]
            dist = haversine_distance_m((longitude, latitude), (lon, lat))
            if dist > radius:
                continue
            results.append(Facility(
                facility_id=f"mock-{fx['category']}-{i}",
                category=fx["category"], name=fx["name"],
                latitude=lat, longitude=lon, distance_m=dist,
                source=self.provider_name))
        results.sort(key=lambda f: f.distance_m)

        if not results:
            return FacilityResult(status=FacilityStatus.UNAVAILABLE,
                                  limitations=["no_facilities_found_within_radius"], **base)
        return FacilityResult(status=FacilityStatus.OK, facilities=results, **base)
