"""SafeRoute AI — Facilities Service facade & factory (PHASE_15, PHASE_29).

Facilities are context only; the service exposes them separately from the
hazard score and never feeds them into the risk engine (Rule 11).

PHASE_29 — two lookup shapes are supported:

* ``get_nearby_facilities`` — a circle around one point (unchanged contract).
* ``get_facilities_near_route`` — a corridor around one or more route
  geometries. This is the shape the SafeRoute UI uses, so the browser no
  longer queries OpenStreetMap itself.

Both return honest records: the measured distance basis, whether a road travel
time could be obtained from a real routing provider, and the provenance of
every attribute (Rule 17, Rule 20).
"""

import dataclasses
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import yaml

from src.facilities.geometry import (
    distance_to_polylines_m,
    normalise_polylines,
    polylines_bbox,
)
from src.facilities.interfaces import FacilitiesProvider
from src.facilities.mock_provider import MockFacilitiesProvider
from src.facilities.overpass_provider import OverpassFacilitiesProvider
from src.facilities.schemas import (
    DISTANCE_ROAD,
    DISTANCE_STRAIGHT_LINE,
    OSM_ATTRIBUTES_NOTE,
    ROAD_TRAVEL_TIME_UNAVAILABLE_NOTE,
    Facility,
    FacilityResult,
    FacilityStatus,
)

DEFAULT_CONFIG_REL = Path("config/facilities.yaml")

#: Straight-line distance statement shown with every corridor lookup.
STRAIGHT_LINE_NOTE = (
    "Distances are straight-line (great-circle) distances, not road-network "
    "distances."
)

#: Attribution per provider. OpenStreetMap data is (c) its contributors (ODbL).
_ATTRIBUTION = {
    "overpass": "(c) OpenStreetMap contributors (ODbL) — openstreetmap.org/copyright",
    "mock_facilities": "Offline test fixture — not a real-world facility record.",
}

#: The attributes note is provider-aware: only real OpenStreetMap data can be
#: described as "as tagged in OpenStreetMap".
_ATTRIBUTES_NOTE = {
    "overpass": OSM_ATTRIBUTES_NOTE,
    "mock_facilities": "Offline test fixture — no OpenStreetMap attributes are attached.",
}

#: Routing providers whose responses are synthetic. Their distances / travel
#: times are never presented as road access, because they are not real.
_FABRICATED_ROUTING_PROVIDER_PREFIXES = ("mock", "fixture", "fake")


def load_facilities_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    if config_path is None:
        root = Path(__file__).resolve().parent.parent.parent
        config_path = (root / DEFAULT_CONFIG_REL).resolve()
    config_path = Path(config_path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Facilities config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_facilities_provider(provider_type: str = "mock", config: Optional[Dict[str, Any]] = None) -> FacilitiesProvider:
    """Factory returning a provider behind the provider-independent interface."""
    cfg = config if config is not None else load_facilities_config()
    providers = cfg.get("providers", {})
    if provider_type == "mock":
        return MockFacilitiesProvider()
    if provider_type == "overpass":
        o = providers.get("overpass", {})
        cats = cfg.get("categories", {})
        tags: Dict[str, Any] = {}
        for name, spec in cats.items():
            if not isinstance(spec, dict):
                continue
            if "osm_tags" in spec:
                tags[name] = spec["osm_tags"]
            elif "osm_tag" in spec:
                tags[name] = spec["osm_tag"]
        base = cfg.get("guardrails", {}).get("overpass_base_url",
                                             o.get("base_url", "https://overpass-api.de/api/interpreter"))
        endpoints = o.get("base_urls") or []
        if not isinstance(endpoints, list):
            endpoints = []
        return OverpassFacilitiesProvider(
            base_url=o.get("base_url", base),
            timeout_seconds=o.get("timeout_seconds", 10.0),
            max_retries=o.get("max_retries", 2),
            backoff_factor_seconds=o.get("backoff_factor_seconds", 0.5),
            osm_tags=tags or None,
            query_gap_seconds=o.get("query_gap_seconds", 0.7),
            query_deadline_seconds=o.get("query_deadline_seconds", 45.0),
            base_urls=endpoints or None,
            max_endpoints=o.get("max_endpoints", 3),
        )
    raise ValueError(f"Unknown facilities provider '{provider_type}'.")


def _uses_fabricated_road_data(routing_provider: Any) -> bool:
    """True when the routing provider returns synthetic geometry/timings."""
    name = str(getattr(routing_provider, "provider_name", "") or "").lower()
    if not name:
        return True
    return name.startswith(_FABRICATED_ROUTING_PROVIDER_PREFIXES)


class FacilitiesService:
    """Thin, provider-independent service around a FacilitiesProvider."""

    def __init__(self, provider: Optional[FacilitiesProvider] = None, config: Optional[Dict[str, Any]] = None):
        self.config = config if config is not None else load_facilities_config()
        if provider is not None:
            self.provider = provider
        else:
            self.provider = create_facilities_provider(
                self.config.get("metadata", {}).get("default_provider", "mock"), self.config)

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #
    def _search_defaults(self) -> Dict[str, Any]:
        return self.config.get("search", {}) or {}

    def _road_access_settings(self) -> Dict[str, Any]:
        return self.config.get("road_access", {}) or {}

    def _resolve_radius(self, radius_m: Optional[float]) -> float:
        s = self._search_defaults()
        radius = radius_m if radius_m is not None else s.get("default_radius_m", 1000.0)
        radius = min(float(radius), float(s.get("max_radius_m", 5000.0)))
        return max(0.0, radius)

    def _resolve_categories(self, categories: Optional[Sequence[str]]) -> List[str]:
        if categories:
            return [str(c) for c in categories]
        return list((self.config.get("categories", {}) or {}).keys())

    def _decorate(self, result: FacilityResult) -> FacilityResult:
        """Attach the standing honest statements to a result."""
        if not result.distance_note:
            result.distance_note = STRAIGHT_LINE_NOTE
        if not result.attributes_note:
            result.attributes_note = _ATTRIBUTES_NOTE.get(result.provider, OSM_ATTRIBUTES_NOTE)
        if not result.source_attribution:
            result.source_attribution = _ATTRIBUTION.get(result.provider, "")
        if not result.road_access_note:
            result.road_access_note = ROAD_TRAVEL_TIME_UNAVAILABLE_NOTE
        return result

    # ------------------------------------------------------------------ #
    # Point lookup (unchanged contract)
    # ------------------------------------------------------------------ #
    def get_nearby_facilities(self, latitude, longitude, radius_m=None, categories=None) -> FacilityResult:
        radius = self._resolve_radius(radius_m)
        cats = self._resolve_categories(categories)
        result = self.provider.get_nearby_facilities(latitude, longitude, radius, list(cats))
        result.distance_basis = DISTANCE_STRAIGHT_LINE
        return self._decorate(result)

    # ------------------------------------------------------------------ #
    # Route-corridor lookup (PHASE_29)
    # ------------------------------------------------------------------ #
    def get_facilities_near_route(
        self,
        polylines: Any,
        radius_m: Optional[float] = None,
        categories: Optional[Sequence[str]] = None,
        include_road_access: bool = True,
        routing_provider: Any = None,
    ) -> FacilityResult:
        """Return the facilities near one or more route geometries.

        The searched area is the union of the supplied corridors, buffered by
        the requested radius. Every returned distance is a STRAIGHT-LINE
        distance from the facility to the nearest point of the route.

        A road distance / road travel time is attached ONLY when a real routing
        provider actually returned one for the nearest facility of a category.
        Otherwise the result states that road travel time is unavailable.
        """
        now = datetime.now(timezone.utc).isoformat()
        radius = self._resolve_radius(radius_m)
        cats = self._resolve_categories(categories)
        lines = normalise_polylines(polylines)

        if not lines:
            result = FacilityResult(
                status=FacilityStatus.INVALID_REQUEST,
                provider=self.provider.provider_name,
                categories_requested=list(cats),
                radius_m=radius,
                retrieved_at=now,
                limitations=["no_route_geometry_supplied"],
                error_message=(
                    "No route geometry was supplied, so the area to search for "
                    "facilities is unknown."
                ),
            )
            return self._decorate(result)

        reference = lines[0][0]
        base = dict(
            provider=self.provider.provider_name,
            categories_requested=list(cats),
            radius_m=radius,
            origin_latitude=reference[1],
            origin_longitude=reference[0],
            retrieved_at=now,
        )

        bbox = polylines_bbox(lines, pad_m=radius)
        if bbox is None:
            result = FacilityResult(
                status=FacilityStatus.INVALID_REQUEST,
                limitations=["no_route_geometry_supplied"],
                error_message="The supplied route geometry could not be used.",
                **base,
            )
            return self._decorate(result)

        raw = self.provider.get_facilities_in_bbox(bbox, list(cats))
        if raw.status != FacilityStatus.OK:
            # Provider failure / empty result: keep the honest status. This is
            # never rewritten into "no hospitals exist" (Rule 20).
            result = FacilityResult(
                status=raw.status,
                provider=raw.provider,
                facilities=[],
                categories_requested=list(cats),
                radius_m=radius,
                origin_latitude=reference[1],
                origin_longitude=reference[0],
                retrieved_at=now,
                limitations=list(raw.limitations),
                error_message=raw.error_message,
            )
            if raw.status == FacilityStatus.UNAVAILABLE:
                result.notes.append(
                    "No facility was found within the searched area. This is the result of "
                    "one OpenStreetMap lookup at one moment in time — it is not proof that "
                    "no hospital exists nearby."
                )
            elif raw.error_message:
                result.notes.append(
                    "The facility data could not be retrieved, so no facility is listed. "
                    "This is a provider failure, not evidence that no hospital exists nearby."
                )
            return self._decorate(result)

        kept: List[Facility] = []
        for facility in raw.facilities:
            distance, closest = distance_to_polylines_m(
                (facility.longitude, facility.latitude), lines
            )
            if distance > radius:
                continue
            kept.append(dataclasses.replace(
                facility,
                distance_m=distance,
                distance_kind=DISTANCE_STRAIGHT_LINE,
            ))
        kept.sort(key=lambda f: f.distance_m)

        if not kept:
            result = FacilityResult(
                status=FacilityStatus.UNAVAILABLE,
                facilities=[],
                limitations=list(raw.limitations) + ["no_facilities_found_within_radius"],
                error_message=None,
                **base,
            )
            result.notes.append(
                "No facility was found within the searched area. This is the result of "
                "one OpenStreetMap lookup at one moment in time — it is not proof that "
                "no hospital exists nearby."
            )
            return self._decorate(result)

        result = FacilityResult(
            status=FacilityStatus.OK,
            facilities=kept,
            limitations=list(raw.limitations),
            **base,
        )
        result.notes.append(
            "Distances are straight-line (great-circle) distances from the route; they "
            "are not road-network distances."
        )
        result.notes.append(
            "Facility names and attributes are "
            f"{_ATTRIBUTES_NOTE.get(result.provider, OSM_ATTRIBUTES_NOTE)}."
        )
        self._attach_road_access(result, kept, lines, include_road_access, routing_provider)
        return self._decorate(result)

    # ------------------------------------------------------------------ #
    # Road access (only from a real routing provider response)
    # ------------------------------------------------------------------ #
    def _attach_road_access(
        self,
        result: FacilityResult,
        facilities: List[Facility],
        lines: List[List[Tuple[float, float]]],
        include_road_access: bool,
        routing_provider: Any,
    ) -> None:
        settings = self._road_access_settings()
        if not include_road_access or not settings.get("enabled", True):
            result.road_access_available = False
            result.road_access_note = (
                "Road travel time is unavailable: road access was not requested for this "
                "lookup."
            )
            return
        if routing_provider is None:
            result.road_access_available = False
            result.road_access_note = (
                "Road travel time is unavailable: no routing provider is available to "
                "answer a road-access request."
            )
            return
        if _uses_fabricated_road_data(routing_provider):
            result.road_access_available = False
            result.road_access_note = (
                "Road travel time is unavailable: the configured routing provider returns "
                "synthetic data, which is never presented as a real road travel time."
            )
            return

        try:
            from src.routing.schemas import Coordinate, RouteRequest
        except Exception:  # pragma: no cover - routing module is always present
            result.road_access_note = (
                "Road travel time is unavailable: the routing interface is unavailable."
            )
            return

        per_category = int(settings.get("max_per_category", 1))
        max_requests = int(settings.get("max_requests", 6))
        provider_name = str(getattr(routing_provider, "provider_name", "") or "")

        nearest_per_category: Dict[str, Facility] = {}
        for facility in facilities:
            if per_category <= 0:
                break
            current = nearest_per_category.get(facility.category)
            if current is None or facility.distance_m < current.distance_m:
                nearest_per_category[facility.category] = facility

        targets = sorted(nearest_per_category.values(), key=lambda f: f.distance_m)[:max_requests]
        if not targets:
            result.road_access_available = False
            result.road_access_note = ROAD_TRAVEL_TIME_UNAVAILABLE_NOTE
            return

        updated: Dict[str, Facility] = {}
        failures: List[str] = []
        for facility in targets:
            reference_point = self._nearest_corridor_point(facility, lines)
            if reference_point is None:
                failures.append(f"{facility.facility_id}: no reference point on the route")
                continue
            try:
                response = routing_provider.get_routes(RouteRequest(
                    origin=Coordinate(latitude=reference_point[1], longitude=reference_point[0]),
                    destination=Coordinate(latitude=facility.latitude, longitude=facility.longitude),
                    alternatives=False,
                ))
            except Exception as exc:  # provider must never break the lookup
                failures.append(f"{facility.facility_id}: {type(exc).__name__}")
                continue

            routes = list(getattr(response, "routes", []) or [])
            if getattr(response, "status", None) is None or not routes:
                failures.append(
                    f"{facility.facility_id}: {getattr(response, 'status', 'unknown')}"
                )
                continue
            route = routes[0]
            updated[facility.facility_id] = dataclasses.replace(
                facility,
                road_distance_m=float(getattr(route, "distance_m", 0.0)),
                road_travel_time_s=float(getattr(route, "duration_s", 0.0)),
                road_access_source=provider_name,
                distance_kind=DISTANCE_STRAIGHT_LINE,
            )

        if updated:
            result.facilities = [updated.get(f.facility_id, f) for f in result.facilities]
            result.road_access_available = True
            result.road_access_note = (
                "Road distance and road travel time are the routing provider's own "
                "estimate for the drive from the nearest point on the route; they are "
                "not live-traffic measurements."
            )
        else:
            result.road_access_available = False
            result.road_access_note = (
                "Road travel time is unavailable: the routing provider did not return a "
                "road route for these facilities."
            )
        if failures:
            result.limitations = list(result.limitations) + ["road_access_unavailable_for_some_facilities"]
            result.notes.append(
                "Road travel time could not be obtained for every nearby facility; "
                "the ones without it are shown as unavailable."
            )

    def _nearest_corridor_point(
        self,
        facility: Facility,
        lines: List[List[Tuple[float, float]]],
    ) -> Optional[Tuple[float, float]]:
        _, closest = distance_to_polylines_m((facility.longitude, facility.latitude), lines)
        return closest
