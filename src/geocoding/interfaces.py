"""SafeRoute AI — provider-independent geocoding interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.geocoding.schemas import GeocodeResult


class GeocodingProvider(ABC):
    """Abstract place-name -> coordinates provider.

    Implementations must never fabricate coordinates: unknown places return
    ``NO_RESULTS`` and provider failures map to explicit error statuses.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'nominatim', 'mock')."""
        pass

    @abstractmethod
    def geocode(self, query: str, limit: int = 5) -> GeocodeResult:
        """Resolve a free-text place query into ranked coordinate candidates."""
        pass

    @abstractmethod
    def reverse(self, latitude: float, longitude: float) -> GeocodeResult:
        """Resolve coordinates back into a human-readable place name."""
        pass
