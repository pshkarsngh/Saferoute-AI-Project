"""SafeRoute AI — Routing Service Factory & Adapter Registry.

Phase ID: PHASE_13
Follows TRD §10, ARCHITECTURE §8.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml

from src.routing.interfaces import RoutingProvider
from src.routing.mock_adapter import MockRoutingAdapter
from src.routing.osrm_adapter import OSRMRoutingAdapter
from src.routing.segmentation import RouteSegmenter

DEFAULT_ROUTING_CONFIG = Path("config/routing.yaml")


def load_routing_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load and parse routing configuration file."""
    if config_path is None:
        workspace_root = Path(__file__).resolve().parent.parent.parent
        config_path = workspace_root / DEFAULT_ROUTING_CONFIG
    else:
        config_path = Path(config_path)

    if not config_path.is_file():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def create_routing_adapter(
    provider_type: Optional[str] = None,
    config_path: Optional[Union[str, Path]] = None,
    **kwargs: Any,
) -> RoutingProvider:
    """Factory creating an instance of RoutingProvider based on config.
    
    Args:
        provider_type: 'mock' or 'osrm'. If None, reads default from config/routing.yaml.
        config_path: Optional path to routing configuration.
        kwargs: Overrides passed to provider constructor.
    """
    config = load_routing_config(config_path)

    # Initialize segmentation engine
    seg_cfg = config.get("segmentation", {})
    segmenter = RouteSegmenter(
        target_segment_length_m=float(seg_cfg.get("target_segment_length_m", 200.0)),
        min_segment_length_m=float(seg_cfg.get("min_segment_length_m", 50.0)),
        max_segment_length_m=float(seg_cfg.get("max_segment_length_m", 500.0)),
    )

    prov_cfg = config.get("provider", {})
    selected_provider = (
        provider_type or prov_cfg.get("default_provider") or "mock"
    ).lower()

    if selected_provider in ["osrm", "live", "openstreetmap"]:
        osrm_cfg = prov_cfg.get("osrm", {})
        return OSRMRoutingAdapter(
            base_url=kwargs.get("base_url", osrm_cfg.get("base_url", "https://router.project-osrm.org")),
            profile=kwargs.get("profile", osrm_cfg.get("profile", "driving")),
            timeout_seconds=float(kwargs.get("timeout_seconds", prov_cfg.get("timeout_seconds", 5.0))),
            max_retries=int(kwargs.get("max_retries", prov_cfg.get("max_retries", 3))),
            backoff_factor=float(kwargs.get("backoff_factor", prov_cfg.get("backoff_factor_seconds", 0.5))),
            segmenter=segmenter,
        )

    # Default to deterministic mock
    mode = kwargs.get("mode", "standard_two_routes")
    return MockRoutingAdapter(mode=mode, segmenter=segmenter)
