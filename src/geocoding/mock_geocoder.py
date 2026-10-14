"""SafeRoute AI — deterministic offline geocoder (tests / demo).

A tiny gazetteer so the app and tests work with zero network access. It never
fabricates coordinates for unknown places: unknown queries return ``NO_RESULTS``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Tuple

from src.geocoding.interfaces import GeocodingProvider
from src.geocoding.schemas import GeocodeCandidate, GeocodeResult, GeocodeStatus

# name fragment -> (display_name, lat, lon)
_GAZETTEER: Dict[str, Tuple[str, float, float]] = {
    "mg road": ("MG Road, Bengaluru, Karnataka, India", 12.9756, 77.6068),
    "bangalore": ("Bengaluru, Karnataka, India", 12.9716, 77.5946),
    "bengaluru": ("Bengaluru, Karnataka, India", 12.9716, 77.5946),
    "koramangala": ("Koramangala, Bengaluru, Karnataka, India", 12.9352, 77.6245),
    "whitefield": ("Whitefield, Bengaluru, Karnataka, India", 12.9698, 77.7499),
    "electronic city": ("Electronic City, Bengaluru, Karnataka, India", 12.8452, 77.6602),
    "delhi": ("New Delhi, Delhi, India", 28.6139, 77.2090),
    "mumbai": ("Mumbai, Maharashtra, India", 19.0760, 72.8777),
    "chennai": ("Chennai, Tamil Nadu, India", 13.0827, 80.2707),
    "hyderabad": ("Hyderabad, Telangana, India", 17.3850, 78.4867),
    "london": ("London, England, United Kingdom", 51.5074, -0.1278),
    "new york": ("New York, United States", 40.7128, -74.0060),
}


class MockGeocoder(GeocodingProvider):
    """Deterministic gazetteer geocoder (no network)."""

    @property
    def provider_name(self) -> str:
        return "mock_geocoder"

    def geocode(self, query: str, limit: int = 5) -> GeocodeResult:
        now = datetime.now(timezone.utc).isoformat()
        q = (query or "").strip().lower()
        if not q:
            return GeocodeResult(status=GeocodeStatus.INVALID_REQUEST, provider=self.provider_name,
                                 query=query, retrieved_at=now, error_message="Empty geocoding query.")

        hits: List[GeocodeCandidate] = []
        for key, (name, lat, lon) in _GAZETTEER.items():
            if key in q or q in key:
                hits.append(GeocodeCandidate(display_name=name, latitude=lat, longitude=lon,
                                             provider=self.provider_name, importance=0.5))
        if not hits:
            return GeocodeResult(status=GeocodeStatus.NO_RESULTS, provider=self.provider_name,
                                 query=query, retrieved_at=now,
                                 error_message="No matching place in offline gazetteer.")
        return GeocodeResult(status=GeocodeStatus.OK, provider=self.provider_name, query=query,
                             candidates=hits[: max(1, int(limit))], retrieved_at=now)

    def reverse(self, latitude: float, longitude: float) -> GeocodeResult:
        now = datetime.now(timezone.utc).isoformat()
        # Nearest gazetteer entry by squared degree distance.
        best = min(_GAZETTEER.values(), key=lambda v: (v[1] - latitude) ** 2 + (v[2] - longitude) ** 2)
        cand = GeocodeCandidate(display_name=best[0], latitude=latitude, longitude=longitude,
                                provider=self.provider_name)
        return GeocodeResult(status=GeocodeStatus.OK, provider=self.provider_name,
                             query=f"{latitude},{longitude}", candidates=[cand], retrieved_at=now)
