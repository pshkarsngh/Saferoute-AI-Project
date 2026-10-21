"""SafeRoute AI — typed application settings (Rule 17, Rule 19).

Combines the non-secret `config/app.yaml` with environment overrides loaded from
the workspace `.env` (Rule 13). This is the single place the real-life runtime
decides which routing / imagery / facilities / geocoding / LLM providers to use.

Defaults target the keyless OpenStreetMap stack (Nominatim geocoding, OSRM
routing, Overpass facilities) plus optional Mapillary imagery and a local Ollama
LLM. Every live provider degrades gracefully to an offline fallback, so the
system is never left in an unusable state.

No secrets are ever emitted by :meth:`Settings.to_safe_dict`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from src.config.env import (
    WORKSPACE_ROOT,
    get_bool,
    get_env,
    get_float,
    get_int,
    load_env,
)

DEFAULT_APP_CONFIG = Path("config/app.yaml")


@dataclass
class Settings:
    """Runtime provider selection and connection settings (non-secret)."""

    # --- Providers -----------------------------------------------------
    routing_provider: str = "osrm"
    facilities_provider: str = "overpass"
    imagery_source: str = "mapillary"
    imagery_fallback_source: str = "workspace_dashcam_v1"
    # PHASE_23B: demo (non-geographically-matched) imagery is OFF by default.
    imagery_demo_mode: bool = False

    # --- Geocoding (Nominatim / OSM) -----------------------------------
    geocoding_enabled: bool = True
    geocoding_provider: str = "nominatim"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_country_codes: str = ""

    # --- Mapillary imagery ---------------------------------------------
    mapillary_max_images: int = 3
    mapillary_search_radius_m: float = 25.0
    mapillary_thumbnail_width: int = 1024
    mapillary_download: bool = True
    mapillary_timeout_seconds: float = 15.0

    # --- LLM (Ollama) --------------------------------------------------
    llm_enabled: bool = True
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "llama3.2"
    # PHASE_28: bounded wait for the local model (see config/app.yaml).
    llm_timeout_seconds: float = 45.0

    # --- Misc ----------------------------------------------------------
    user_agent: str = "SafeRouteAI/1.0 (road-safety research; contact: local)"
    static_dir: str = "frontend"
    host: str = "127.0.0.1"
    port: int = 8000

    # Secrets (never serialised) ----------------------------------------
    mapillary_token: str = field(default="", repr=False)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Return all non-secret settings for health/debug output."""
        data = asdict(self)
        data.pop("mapillary_token", None)
        data["mapillary_token_present"] = bool(self.mapillary_token)
        return data


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def load_settings(
    config_path: Optional[Union[str, Path]] = None,
    env_path: Optional[Union[str, Path]] = None,
) -> Settings:
    """Load settings from `config/app.yaml` plus `.env`/environment overrides."""
    load_env(env_path)

    cfg_path = Path(config_path) if config_path else (WORKSPACE_ROOT / DEFAULT_APP_CONFIG)
    cfg = _load_yaml(cfg_path)
    app = cfg.get("app", {}) or {}
    geo = app.get("geocoding", {}) or {}
    imag = app.get("imagery", {}) or {}
    llm = app.get("llm", {}) or {}
    server = app.get("server", {}) or {}

    s = Settings(
        routing_provider=str(app.get("routing_provider", "osrm")),
        facilities_provider=str(app.get("facilities_provider", "overpass")),
        imagery_source=str(app.get("imagery_source", "mapillary")),
        imagery_fallback_source=str(app.get("imagery_fallback_source", "workspace_dashcam_v1")),
        imagery_demo_mode=bool(imag.get("demo_mode", False)),
        geocoding_enabled=bool(geo.get("enabled", True)),
        geocoding_provider=str(geo.get("provider", "nominatim")),
        nominatim_base_url=str(geo.get("base_url", "https://nominatim.openstreetmap.org")),
        geocoding_country_codes=str(geo.get("country_codes", "")),
        mapillary_max_images=int(imag.get("max_images_per_segment", 3)),
        mapillary_search_radius_m=float(imag.get("search_radius_meters", 25.0)),
        mapillary_thumbnail_width=int(imag.get("thumbnail_width", 1024)),
        mapillary_download=bool(imag.get("download_thumbnails", True)),
        mapillary_timeout_seconds=float(imag.get("timeout_seconds", 15.0)),
        llm_enabled=bool(llm.get("enabled", True)),
        llm_base_url=str(llm.get("base_url", "http://127.0.0.1:11434")),
        llm_model=str(llm.get("model", "llama3.2")),
        llm_timeout_seconds=float(llm.get("timeout_seconds", 45.0)),
        user_agent=str(app.get("user_agent", "SafeRouteAI/1.0 (road-safety research)")),
        static_dir=str(app.get("static_dir", "frontend")),
        host=str(server.get("host", "127.0.0.1")),
        port=int(server.get("port", 8000)),
    )

    # ---- Environment overrides (highest precedence) -------------------
    s.routing_provider = get_env("SAFEROUTE_ROUTING_PROVIDER", s.routing_provider)
    s.facilities_provider = get_env("SAFEROUTE_FACILITIES_PROVIDER", s.facilities_provider)
    s.imagery_source = get_env("SAFEROUTE_IMAGERY_SOURCE", s.imagery_source)
    s.imagery_demo_mode = get_bool("SAFEROUTE_IMAGERY_DEMO_MODE", s.imagery_demo_mode)
    s.geocoding_provider = get_env("SAFEROUTE_GEOCODING_PROVIDER", s.geocoding_provider)
    s.geocoding_enabled = get_bool("SAFEROUTE_GEOCODING_ENABLED", s.geocoding_enabled)
    s.nominatim_base_url = get_env("NOMINATIM_BASE_URL", s.nominatim_base_url)
    s.geocoding_country_codes = get_env("SAFEROUTE_GEOCODING_COUNTRY_CODES", s.geocoding_country_codes)
    s.user_agent = get_env("SAFEROUTE_USER_AGENT", s.user_agent)
    s.static_dir = get_env("SAFEROUTE_STATIC_DIR", s.static_dir)
    s.host = get_env("SAFEROUTE_HOST", s.host)
    s.port = get_int("SAFEROUTE_PORT", s.port)

    # LLM: an explicit OLLAMA_BASE_URL implies enabling.
    ollama_base = get_env("OLLAMA_BASE_URL")
    if ollama_base:
        s.llm_base_url = ollama_base
        s.llm_enabled = True
    s.llm_enabled = get_bool("SAFEROUTE_LLM_ENABLED", s.llm_enabled)
    s.llm_model = get_env("OLLAMA_MODEL", s.llm_model)
    s.llm_timeout_seconds = get_float("SAFEROUTE_LLM_TIMEOUT_SECONDS", s.llm_timeout_seconds)

    # Imagery: token presence enables the live Mapillary source.
    s.mapillary_token = get_env("MAPILLARY_ACCESS_TOKEN", "") or ""
    s.mapillary_max_images = get_int("SAFEROUTE_MAPILLARY_MAX_IMAGES", s.mapillary_max_images)

    return s
