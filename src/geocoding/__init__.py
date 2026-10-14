"""SafeRoute AI — Geocoding package.

Place-name -> coordinates so real users can type a destination instead of raw
lat/long. Keyless OpenStreetMap/Nominatim by default (Rule 8, Rule 19).
"""

from src.geocoding.schemas import (
    GeocodeCandidate,
    GeocodeResult,
    GeocodeStatus,
)
from src.geocoding.interfaces import GeocodingProvider
from src.geocoding.nominatim import NominatimGeocoder
from src.geocoding.mock_geocoder import MockGeocoder
from src.geocoding.factory import create_geocoding_provider, load_geocoding_config

__version__ = "geocoding-v1"

__all__ = [
    "GeocodeCandidate",
    "GeocodeResult",
    "GeocodeStatus",
    "GeocodingProvider",
    "NominatimGeocoder",
    "MockGeocoder",
    "create_geocoding_provider",
    "load_geocoding_config",
    "__version__",
]
