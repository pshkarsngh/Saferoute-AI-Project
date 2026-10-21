"""SafeRoute AI — OpenStreetMap (Overpass) Facilities Provider.

Phase ID: PHASE_15, extended in PHASE_29 (corridor lookups + honest attributes).
Data (c) OpenStreetMap contributors, ODbL — free, no API key.
Facilities are CONTEXT ONLY and never enter the hazard score (Rule 11).
Never fabricates facilities; failures map to explicit statuses (Rule 20).

Distances produced here are STRAIGHT-LINE (great-circle) distances only. A
road distance / road travel time is never estimated by this provider — it is
only ever attached by the service when a real routing provider returned one.

The raw OpenStreetMap tags are echoed back verbatim and are explicitly flagged
as NOT independently verified.
"""

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.facilities.interfaces import FacilitiesProvider
from src.facilities.schemas import (
    DISTANCE_STRAIGHT_LINE,
    Facility,
    FacilityResult,
    FacilityStatus,
    bounded_osm_tags,
)
from src.routing.segmentation import haversine_distance_m

#: PHASE_29: one category may match several OpenStreetMap values, so every
#: category carries a LIST of "key=value" selectors.
DEFAULT_OSM_TAGS: Dict[str, List[str]] = {
    "hospital": ["amenity=hospital"],
    "medical": [
        "amenity=pharmacy",
        "amenity=clinic",
        "amenity=doctors",
        "amenity=dentist",
        "amenity=doctors_office",
    ],
    "police": ["amenity=police"],
    "fuel": [
        "amenity=fuel",
        "amenity=fuel_station",
        "amenity=petrol_station",
        "amenity=charging_station",
    ],
    "hotel": [
        "tourism=hotel",
        "tourism=motel",
        "tourism=hostel",
        "tourism=guest_house",
        "tourism=bed_and_breakfast",
        "tourism=chalet",
    ],
    "restaurant": ["amenity=restaurant"],
}

#: OSM tags echoed back first, in this order, so the most useful (and the most
#: easily misread) attributes are never dropped by the payload bound.
_OSM_TAG_PRIORITY: Tuple[str, ...] = (
    "name",
    "amenity",
    "tourism",
    "healthcare",
    "emergency",
    "opening_hours",
    "operator",
    "operator:type",
    "beds",
    "capacity",
    "staff",
    "wheelchair",
    "phone",
    "website",
    "addr:street",
    "addr:city",
)

#: Attribution for the underlying data source.
OSM_ATTRIBUTION = "(c) OpenStreetMap contributors (ODbL) — openstreetmap.org/copyright"


def _normalise_osm_tags(raw: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Accept either ``{category: "k=v"}`` or ``{category: ["k=v", …]}``."""
    if not raw:
        return {k: list(v) for k, v in DEFAULT_OSM_TAGS.items()}
    out: Dict[str, List[str]] = {}
    for category, value in raw.items():
        if isinstance(value, str):
            out[category] = [value]
        elif isinstance(value, (list, tuple)):
            tags = [str(item) for item in value if isinstance(item, str) and "=" in item]
            if tags:
                out[category] = tags
    return out


def _prioritised_tags(tags: Dict[str, str]) -> Dict[str, str]:
    """Order the raw tags so the most meaningful ones survive the payload bound."""
    ordered: Dict[str, str] = {}
    for key in _OSM_TAG_PRIORITY:
        if key in tags:
            ordered[key] = tags[key]
    for key, value in tags.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


class OverpassFacilitiesProvider(FacilitiesProvider):
    """Live facilities provider backed by the OpenStreetMap Overpass API.

    PHASE_29: the public Overpass instances are frequently busy and answer with
    HTTP 502/504 or simply stall. The provider therefore fails over between
    mirror instances (the resilience the browser client used to have) and keeps
    the whole lookup inside one time budget.
    """

    def __init__(
        self,
        base_url: str = "https://overpass-api.de/api/interpreter",
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        backoff_factor_seconds: float = 0.5,
        osm_tags: Optional[Dict[str, Any]] = None,
        query_gap_seconds: float = 0.7,
        query_deadline_seconds: float = 45.0,
        base_urls: Optional[List[str]] = None,
        max_endpoints: int = 3,
    ):
        self.base_url = base_url
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)
        self.backoff_factor_seconds = float(backoff_factor_seconds)
        self.osm_tags = _normalise_osm_tags(osm_tags)
        self.query_gap_seconds = float(query_gap_seconds)
        self.query_deadline_seconds = float(query_deadline_seconds)
        endpoints = [u for u in (base_urls or []) if isinstance(u, str) and u.strip()]
        if not endpoints and base_url:
            endpoints = [base_url]
        self.base_urls = endpoints
        self.max_endpoints = max(1, int(max_endpoints))

    @property
    def provider_name(self) -> str:
        return "overpass"

    # ------------------------------------------------------------------ #
    # Query construction
    # ------------------------------------------------------------------ #
    def _category_query(self, category: str, area_filter: str) -> str:
        """One small Overpass query for a single category.

        The public Overpass instance reliably serves small, single-category
        queries; a single combined multi-category query is regularly refused or
        times out, so each category is queried separately.
        """
        selectors: List[str] = []
        for tag in self.osm_tags.get(category, []):
            key, value = tag.split("=", 1)
            selectors.append(f'node["{key}"="{value}"]({area_filter});')
            selectors.append(f'way["{key}"="{value}"]({area_filter});')
        if not selectors:
            return ""
        body = "\n  ".join(selectors)
        return f"[out:json][timeout:{int(self.timeout_seconds)}];\n(\n  {body}\n);\nout center tags;"

    # ------------------------------------------------------------------ #
    # Network access
    # ------------------------------------------------------------------ #
    def _fetch_category(
        self,
        category: str,
        area_filter: str,
        deadline: Optional[float] = None,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Fetch one category. Returns ``(payload, failure_kind)``.

        ``failure_kind`` is ``""`` on success, otherwise one of
        ``"rate_limited"`` / ``"timeout"`` / ``"budget"`` / ``"error"``.
        """
        query = self._category_query(category, area_filter)
        if not query:
            return None, "error"
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        last_err = "unknown error"
        kinds: List[str] = []

        for endpoint in self.base_urls[: self.max_endpoints]:
            for attempt in range(self.max_retries + 1):
                if deadline is not None and time.monotonic() > deadline:
                    return None, "budget"
                try:
                    req = urllib.request.Request(
                        endpoint,
                        data=data,
                        headers={"User-Agent": "SafeRouteAI/1.0 (PHASE_29)"},
                    )
                    with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                        return json.loads(resp.read().decode("utf-8")), ""
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        kinds.append("rate_limited")
                        break  # rate limiting is endpoint-wide: try the next mirror
                    last_err = f"HTTP {e.code}"
                except (socket.timeout, TimeoutError):
                    last_err = "request timed out"
                    kinds.append("timeout")
                except urllib.error.URLError as e:
                    reason = getattr(e, "reason", e)
                    if isinstance(reason, (socket.timeout, TimeoutError)) or \
                            "timed out" in str(reason).lower():
                        last_err = "request timed out"
                        kinds.append("timeout")
                    else:
                        last_err = f"URLError: {reason}"
                except Exception as e:  # JSON / unexpected
                    last_err = f"{type(e).__name__}: {e}"
                if attempt < self.max_retries:
                    time.sleep(self.backoff_factor_seconds * (2 ** attempt))

        if "rate_limited" in kinds:
            return None, "rate_limited"
        if "timeout" in kinds:
            return None, "timeout"
        return None, "error"

    def _run_category_queries(
        self,
        categories: List[str],
        area_filter: str,
    ) -> Tuple[List[Dict[str, Any]], List[str], Optional[str]]:
        """Query every category. Returns ``(elements, limitations, failure_kind)``.

        ``failure_kind`` is ``None`` when at least one category succeeded.
        """
        elements: List[Dict[str, Any]] = []
        limitations: List[str] = []
        failures: List[str] = []
        kinds: List[str] = []
        queried = 0
        succeeded = 0
        started = time.monotonic()
        deadline = (started + self.query_deadline_seconds) if self.query_deadline_seconds > 0 else None

        for index, category in enumerate(categories):
            if deadline is not None and time.monotonic() > deadline:
                # The overall lookup budget is spent: the remaining categories are
                # NOT attempted and the partial result is disclosed.
                remaining = len(categories) - index
                limitations.append(f"provider_query_budget_exhausted:{remaining}_categories_not_queried")
                break
            queried += 1
            payload, failure = self._fetch_category(category, area_filter, deadline)
            if payload is None:
                failures.append(f"{category}: {failure}")
                kinds.append(failure)
            else:
                succeeded += 1
                elements.extend(payload.get("elements", []) or [])
            if index < len(categories) - 1 and self.query_gap_seconds > 0:
                time.sleep(self.query_gap_seconds)

        if succeeded == 0:
            # Nothing could be answered. Report the most specific honest status —
            # never "there are no facilities here" (Rule 20).
            if queried == 0 or "budget" in kinds:
                return [], limitations, "budget"
            kind = "error"
            if "rate_limited" in kinds:
                kind = "rate_limited"
            elif "timeout" in kinds:
                kind = "timeout"
            return [], [f"provider_query_failed:{len(failures)}"], kind
        if failures:
            limitations.append(f"partial_provider_failure:{len(failures)}_of_{len(categories)}")
        return elements, limitations, None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_nearby_facilities(self, latitude, longitude, radius_m=None, categories=None):
        now = datetime.now(timezone.utc).isoformat()
        radius = float(radius_m if radius_m is not None else 1000.0)
        cats = list(categories) if categories else list(self.osm_tags.keys())
        base = dict(provider=self.provider_name, categories_requested=cats, radius_m=radius,
                    origin_latitude=latitude, origin_longitude=longitude, retrieved_at=now)

        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            return FacilityResult(status=FacilityStatus.INVALID_REQUEST,
                                  error_message="Invalid coordinates.", **base)

        area_filter = f"around:{radius:.0f},{latitude},{longitude}"
        elements, limitations, failure = self._run_category_queries(cats, area_filter)
        if failure is not None:
            return self._failure_result(failure, cats, limitations, base)
        return self._build_result(elements, cats, latitude, longitude, radius, base, limitations)

    def get_facilities_in_bbox(self, bbox, categories=None):
        """Return the facilities inside ``bbox`` = (south, west, north, east)."""
        now = datetime.now(timezone.utc).isoformat()
        south, west, north, east = (float(v) for v in bbox)
        cats = list(categories) if categories else list(self.osm_tags.keys())
        centre_lat = (south + north) / 2.0
        centre_lon = (west + east) / 2.0
        base = dict(provider=self.provider_name, categories_requested=cats, radius_m=0.0,
                    origin_latitude=centre_lat, origin_longitude=centre_lon, retrieved_at=now)

        if not (-90.0 <= centre_lat <= 90.0) or not (-180.0 <= centre_lon <= 180.0):
            return FacilityResult(status=FacilityStatus.INVALID_REQUEST,
                                  error_message="Invalid bounding box.", **base)

        area_filter = f"{south:.6f},{west:.6f},{north:.6f},{east:.6f}"
        elements, limitations, failure = self._run_category_queries(cats, area_filter)
        if failure is not None:
            return self._failure_result(failure, cats, limitations, base)

        facilities = self._to_facilities(elements, cats, (centre_lon, centre_lat))
        if not facilities:
            return FacilityResult(
                status=FacilityStatus.UNAVAILABLE,
                limitations=list(limitations) + ["no_facilities_found_within_radius"],
                **base,
            )
        return FacilityResult(
            status=FacilityStatus.OK,
            facilities=facilities,
            limitations=list(limitations),
            **base,
        )

    # ------------------------------------------------------------------ #
    # Parsing helpers
    # ------------------------------------------------------------------ #
    def _failure_result(self, failure: str, cats, limitations, base) -> FacilityResult:
        status = {
            "rate_limited": FacilityStatus.RATE_LIMITED,
            "timeout": FacilityStatus.PROVIDER_TIMEOUT,
        }.get(failure, FacilityStatus.PROVIDER_ERROR)
        message = {
            "rate_limited": "The facility data provider rate-limited the request.",
            "timeout": "The facility data provider did not respond in time.",
            "budget": (
                "The facility data lookup ran out of its time budget before any "
                "category could be answered."
            ),
        }.get(failure, "The facility data provider returned an error.")
        return FacilityResult(
            status=status,
            error_message=message,
            limitations=list(limitations) + [f"provider_{failure}"],
            **base,
        )

    def _tag_index(self) -> Dict[str, Tuple[str, str]]:
        """Map "key=value" → (category, subtype)."""
        index: Dict[str, Tuple[str, str]] = {}
        for category, tags in self.osm_tags.items():
            for tag in tags:
                key, value = tag.split("=", 1)
                index.setdefault(f"{key}={value}", (category, value))
        return index

    def _to_facilities(
        self,
        elements: List[Dict[str, Any]],
        cats: List[str],
        reference: Tuple[float, float],
    ) -> List[Facility]:
        index = self._tag_index()
        out: List[Facility] = []
        for el in elements:
            tags = el.get("tags", {}) or {}
            category = None
            subtype = ""
            for key in ("amenity", "tourism"):
                value = tags.get(key)
                if value is None:
                    continue
                hit = index.get(f"{key}={value}")
                if hit is not None:
                    category, subtype = hit
                    break
            if category is None or category not in cats:
                continue
            if el.get("type") == "node":
                lat, lon = el.get("lat"), el.get("lon")
            else:
                center = el.get("center", {}) or {}
                lat, lon = center.get("lat"), center.get("lon")
            if lat is None or lon is None:
                continue
            dist = haversine_distance_m(reference, (lon, lat))
            out.append(Facility(
                facility_id=f"osm-{el.get('type')}-{el.get('id')}",
                category=category,
                subtype=subtype,
                name=tags.get("name") or f"{category.title()} (unnamed)",
                latitude=lat, longitude=lon, distance_m=dist,
                distance_kind=DISTANCE_STRAIGHT_LINE,
                source=self.provider_name,
                osm_tags=bounded_osm_tags(_prioritised_tags(tags)),
                attributes_verified=False,
            ))
        out.sort(key=lambda f: f.distance_m)
        return out

    def _build_result(self, elements, cats, latitude, longitude, radius, base, limitations) -> FacilityResult:
        facilities = self._to_facilities(elements, cats, (longitude, latitude))
        # The circle query is authoritative for "nearby"; keep only what is
        # genuinely inside the requested radius.
        facilities = [f for f in facilities if f.distance_m <= radius]
        if not facilities:
            return FacilityResult(
                status=FacilityStatus.UNAVAILABLE,
                limitations=list(limitations) + ["no_facilities_found_within_radius"],
                **base,
            )
        return FacilityResult(
            status=FacilityStatus.OK,
            facilities=facilities,
            limitations=list(limitations),
            **base,
        )
