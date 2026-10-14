"""SafeRoute AI — geocoding provider factory (Rule 8, Rule 19)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from src.geocoding.interfaces import GeocodingProvider
from src.geocoding.mock_geocoder import MockGeocoder
from src.geocoding.nominatim import NominatimGeocoder

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_REL = Path("config/geocoding.yaml")


def load_geocoding_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    path = Path(config_path) if config_path else (WORKSPACE_ROOT / DEFAULT_CONFIG_REL)
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def create_geocoding_provider(
    provider_type: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    settings: Any = None,
) -> GeocodingProvider:
    """Build a geocoding provider; defaults to keyless Nominatim."""
    cfg = config if config is not None else load_geocoding_config()
    selected = (provider_type or cfg.get("provider", "nominatim") or "nominatim").lower()

    if selected in ("mock", "offline"):
        return MockGeocoder()

    nom = cfg.get("nominatim", {}) or {}
    base_url = nom.get("base_url", "https://nominatim.openstreetmap.org")
    user_agent = nom.get("user_agent", "SafeRouteAI/1.0 (road-safety research)")
    timeout = float(nom.get("timeout_seconds", 10.0))
    country_codes = nom.get("country_codes", "")

    if settings is not None:
        base_url = getattr(settings, "nominatim_base_url", base_url)
        user_agent = getattr(settings, "user_agent", user_agent)
        country_codes = getattr(settings, "geocoding_country_codes", country_codes) or country_codes

    return NominatimGeocoder(
        base_url=base_url,
        user_agent=user_agent,
        timeout_seconds=timeout,
        country_codes=country_codes,
    )
