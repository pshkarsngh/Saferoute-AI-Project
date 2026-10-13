"""SafeRoute AI — Facilities Service facade & factory (PHASE_15).

Facilities are context only; the service exposes them separately from the
hazard score and never feeds them into the risk engine (Rule 11).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from src.facilities.interfaces import FacilitiesProvider
from src.facilities.mock_provider import MockFacilitiesProvider
from src.facilities.overpass_provider import OverpassFacilitiesProvider
from src.facilities.schemas import FacilityResult

DEFAULT_CONFIG_REL = Path("config/facilities.yaml")


def load_facilities_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    if config_path is None:
        root = Path(__file__).resolve().parent.parent.parent
        config_path = (root / DEFAULT_CONFIG_REL).resolve()
    config_path = Path(config_path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Facilities config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_facilities_provider(provider_type: str = "mock", config: Optional[Dict] = None) -> FacilitiesProvider:
    """Factory returning a provider behind the provider-independent interface."""
    cfg = config if config is not None else load_facilities_config()
    providers = cfg.get("providers", {})
    if provider_type == "mock":
        return MockFacilitiesProvider()
    if provider_type == "overpass":
        o = providers.get("overpass", {})
        cats = cfg.get("categories", {})
        tags = {name: spec["osm_tag"] for name, spec in cats.items() if "osm_tag" in spec}
        base = cfg.get("guardrails", {}).get("overpass_base_url", o.get("base_url", "https://overpass-api.de/api/interpreter"))
        return OverpassFacilitiesProvider(
            base_url=o.get("base_url", base),
            timeout_seconds=o.get("timeout_seconds", 10.0),
            max_retries=o.get("max_retries", 2),
            backoff_factor_seconds=o.get("backoff_factor_seconds", 0.5),
            osm_tags=tags,
        )
    raise ValueError(f"Unknown facilities provider '{provider_type}'.")


class FacilitiesService:
    """Thin, provider-independent service around a FacilitiesProvider."""

    def __init__(self, provider: Optional[FacilitiesProvider] = None, config: Optional[Dict] = None):
        self.config = config if config is not None else load_facilities_config()
        if provider is not None:
            self.provider = provider
        else:
            self.provider = create_facilities_provider(
                self.config.get("metadata", {}).get("default_provider", "mock"), self.config)

    def get_nearby_facilities(self, latitude, longitude, radius_m=None, categories=None) -> FacilityResult:
        s = self.config.get("search", {})
        radius = radius_m if radius_m is not None else s.get("default_radius_m", 1000.0)
        radius = min(float(radius), float(s.get("max_radius_m", 5000.0)))
        cats = categories if categories else list(self.config.get("categories", {}).keys())
        return self.provider.get_nearby_facilities(latitude, longitude, radius, list(cats))
