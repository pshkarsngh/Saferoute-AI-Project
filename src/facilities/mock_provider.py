"""SafeRoute AI — Deterministic Mock Facilities Provider (PHASE_15).

Offline fixtures for tests/demo. No network. Facilities are context only
(Rule 11) and are always labelled with source="mock_facilities".

PHASE_29: the fixtures are clearly marked as offline test data. They carry no
OpenStreetMap tags, so nothing about them can be mistaken for a real-world
facility record or a verified attribute.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.facilities.interfaces import FacilitiesProvider
from src.facilities.schemas import (
    DISTANCE_STRAIGHT_LINE,
    Facility,
    FacilityResult,
    FacilityStatus,
)
from src.routing.segmentation import haversine_distance_m

#: Offsets (in degrees) from the origin so a deterministic set of nearby
#: facilities is produced for any origin. ~0.001 deg is ~111 m.
_FIXTURES: List[Dict] = [
    {"category": "hospital", "subtype": "hospital", "name": "City General Hospital",
     "dlat": 0.004, "dlon": 0.003},
    {"category": "medical", "subtype": "pharmacy", "name": "Wellness Pharmacy",
     "dlat": 0.001, "dlon": -0.001},
    {"category": "police", "subtype": "police", "name": "Central Police Station",
     "dlat": -0.002, "dlon": 0.002},
    {"category": "fuel", "subtype": "fuel", "name": "Highway Fuel Pump",
     "dlat": 0.003, "dlon": -0.004},
    {"category": "hotel", "subtype": "hotel", "name": "Transit Hotel",
     "dlat": -0.003, "dlon": -0.002},
    {"category": "restaurant", "subtype": "restaurant", "name": "Roadside Restaurant",
     "dlat": 0.002, "dlon": 0.005},
]

#: Categories the mock provider knows about.
MOCK_CATEGORIES = sorted({fx["category"] for fx in _FIXTURES})


class MockFacilitiesProvider(FacilitiesProvider):
    """Deterministic offline facilities provider for reproducible tests/demo."""

    def __init__(self, available: bool = True, error_mode: Optional[str] = None):
        self.available = available
        self.error_mode = error_mode

    @property
    def provider_name(self) -> str:
        return "mock_facilities"

    def _base(self, cats, radius, latitude, longitude):
        now = datetime.now(timezone.utc).isoformat()
        return dict(provider=self.provider_name, categories_requested=cats,
                    radius_m=radius, origin_latitude=latitude, origin_longitude=longitude,
                    retrieved_at=now)

    def _error_result(self, cats, radius, latitude, longitude) -> Optional[FacilityResult]:
        if self.error_mode == "timeout":
            return FacilityResult(status=FacilityStatus.PROVIDER_TIMEOUT,
                                  error_message="Mock provider timeout.", **self._base(cats, radius, latitude, longitude))
        if self.error_mode == "provider_error":
            return FacilityResult(status=FacilityStatus.PROVIDER_ERROR,
                                  error_message="Mock provider 5xx error.", **self._base(cats, radius, latitude, longitude))
        if self.error_mode == "rate_limited":
            return FacilityResult(status=FacilityStatus.RATE_LIMITED,
                                  error_message="Mock provider rate limited.", **self._base(cats, radius, latitude, longitude))
        return None

    def get_nearby_facilities(self, latitude, longitude, radius_m=None, categories=None):
        radius = float(radius_m if radius_m is not None else 1000.0)
        cats = list(categories) if categories else list(MOCK_CATEGORIES)
        base = self._base(cats, radius, latitude, longitude)

        failure = self._error_result(cats, radius, latitude, longitude)
        if failure is not None:
            return failure

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
                category=fx["category"], subtype=fx["subtype"], name=fx["name"],
                latitude=lat, longitude=lon, distance_m=dist,
                distance_kind=DISTANCE_STRAIGHT_LINE,
                source=self.provider_name))
        results.sort(key=lambda f: f.distance_m)

        if not results:
            return FacilityResult(status=FacilityStatus.UNAVAILABLE,
                                  limitations=["no_facilities_found_within_radius"], **base)
        return FacilityResult(status=FacilityStatus.OK, facilities=results, **base)

    def get_facilities_in_bbox(self, bbox, categories=None) -> FacilityResult:
        """Return the mock fixtures that fall inside ``bbox`` = (south, west, north, east)."""
        south, west, north, east = (float(v) for v in bbox)
        centre_lat = (south + north) / 2.0
        centre_lon = (west + east) / 2.0
        cats = list(categories) if categories else list(MOCK_CATEGORIES)
        base = self._base(cats, 0.0, centre_lat, centre_lon)

        failure = self._error_result(cats, 0.0, centre_lat, centre_lon)
        if failure is not None:
            return failure

        results: List[Facility] = []
        for i, fx in enumerate(_FIXTURES):
            if fx["category"] not in cats:
                continue
            lat = centre_lat + fx["dlat"]
            lon = centre_lon + fx["dlon"]
            if not (south <= lat <= north and west <= lon <= east):
                continue
            dist = haversine_distance_m((centre_lon, centre_lat), (lon, lat))
            results.append(Facility(
                facility_id=f"mock-{fx['category']}-{i}",
                category=fx["category"], subtype=fx["subtype"], name=fx["name"],
                latitude=lat, longitude=lon, distance_m=dist,
                distance_kind=DISTANCE_STRAIGHT_LINE,
                source=self.provider_name))
        results.sort(key=lambda f: f.distance_m)

        if not results:
            return FacilityResult(status=FacilityStatus.UNAVAILABLE,
                                  limitations=["no_facilities_found_within_radius"], **base)
        return FacilityResult(status=FacilityStatus.OK, facilities=results, **base)
