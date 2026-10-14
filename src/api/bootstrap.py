"""SafeRoute AI — runtime bootstrap (PHASE_19 wiring).

Constructs the live, real-world pipeline from :class:`Settings`:

    routing  -> OSRM (keyless OSM)      [mock fallback only if OSRM unavailable]
    imagery  -> Mapillary (token)       [local archive fallback, disclosed]
    facilities -> Overpass (keyless OSM)
    llm      -> local Ollama            [deterministic fallback if unreachable]
    geocoding  -> Nominatim (keyless OSM)

The unit tests keep constructing :class:`SafetyAnalysisPipeline` directly with
offline fakes, so this module is the ONLY place live providers are selected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.api.pipeline import SafetyAnalysisPipeline
from src.config import Settings, load_settings
from src.facilities.service import FacilitiesService, create_facilities_provider
from src.geocoding.factory import create_geocoding_provider
from src.geocoding.interfaces import GeocodingProvider
from src.imagery.adapter import PermittedImageryAdapter
from src.imagery.mapillary_provider import MapillaryImageryProvider
from src.llm.explainer import GroundedExplanationService
from src.routing.adapter import create_routing_adapter

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def build_imagery_provider(settings: Settings):
    """Mapillary when a token is present, else the permitted local adapter.

    PHASE_23B: the local adapter no longer fabricates geographic coordinates, so
    it never presents sample imagery as evidence for a real route segment. It is
    placed in demo mode only when explicitly configured (Rule 9, Rule 20).
    """
    local = PermittedImageryAdapter(demo_mode=settings.imagery_demo_mode)
    if settings.imagery_source == "mapillary" and settings.mapillary_token:
        return MapillaryImageryProvider(
            token=settings.mapillary_token,
            max_images=settings.mapillary_max_images,
            search_radius_m=settings.mapillary_search_radius_m,
            thumbnail_width=settings.mapillary_thumbnail_width,
            download_thumbnails=settings.mapillary_download,
            http=None,
            fallback=local,
            is_source_permitted=local.is_source_permitted,
        )
    # No token: honest local mode (real imagery only; demo only if explicitly on).
    return local


def build_explainer(settings: Settings) -> GroundedExplanationService:
    enabled = bool(settings.llm_enabled and settings.llm_base_url)
    return GroundedExplanationService(
        base_url=settings.llm_base_url or None,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        enabled=enabled,
    )


def build_pipeline(settings: Optional[Settings] = None) -> SafetyAnalysisPipeline:
    """Assemble the live pipeline from settings."""
    settings = settings or load_settings()
    routing = create_routing_adapter(settings.routing_provider)
    imagery = build_imagery_provider(settings)
    facilities = FacilitiesService(provider=create_facilities_provider(settings.facilities_provider))
    explainer = build_explainer(settings)
    return SafetyAnalysisPipeline(
        routing_provider=routing,
        imagery_adapter=imagery,
        facilities_service=facilities,
        explainer=explainer,
    )


def build_geocoder(settings: Optional[Settings] = None) -> GeocodingProvider:
    settings = settings or load_settings()
    return create_geocoding_provider(settings.geocoding_provider, settings=settings)
