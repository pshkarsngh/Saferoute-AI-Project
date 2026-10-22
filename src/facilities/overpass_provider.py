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
import re
import socket
import sys
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


def _host_of(endpoint: str) -> str:
    """The host part of an Overpass URL, for readable diagnostics."""
    try:
        return urllib.parse.urlparse(endpoint).netloc
    except Exception:  # pragma: no cover - diagnostics must never break a lookup
        return endpoint


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
    def _server_timeout_tag(self) -> int:
        """The Overpass server-side execution budget, in seconds.

        Overpass caps the ``[timeout:…]`` server tag at 180 s; asking for more
        makes the instance reject the query outright.
        """
        return max(1, min(180, int(self.timeout_seconds)))

    def _category_query(self, category: str, area_filter: str) -> str:
        """One small Overpass query for a single category.

        Kept as the per-category FALLBACK path. Measured behaviour (PHASE_30)
        showed that asking the public instance for one category at a time is
        what actually fails: each request queues behind other users' traffic
        and the instance answers 30-60 s later, or 429/502/504 outright. One
        combined request carrying every category is answered in seconds.
        """
        selectors: List[str] = []
        for tag in self.osm_tags.get(category, []):
            key, value = tag.split("=", 1)
            selectors.append(f'node["{key}"="{value}"]({area_filter});')
            selectors.append(f'way["{key}"="{value}"]({area_filter});')
        if not selectors:
            return ""
        body = "\n  ".join(selectors)
        return f"[out:json][timeout:{self._server_timeout_tag()}];\n(\n  {body}\n);\nout center tags;"

    def _combined_query(self, categories: List[str], area_filter: str) -> str:
        """One Overpass query that covers every requested category at once.

        PHASE_30 (measured): the public Overpass instances are queue-bound, not
        query-bound. Asking for all categories in a single request returned
        4145 facilities for a 140 km corridor in 15.7 s, while the same data
        requested one category at a time needed 6 requests of 30-60 s each and
        exhausted the lookup budget. The 502/504 answers seen during testing
        carry the instance's own message ("currently at capacity. All query
        workers are busy and the request queue is full") — they are capacity
        signals, not a rejection of the combined selector.

        The selectors are derived from exactly the same OSM tags that
        ``_tag_index`` uses to map an element back to its category, so a
        combined answer carries the same category and subtype information as
        the per-category path.
        """
        by_key: Dict[str, List[str]] = {}
        for category in categories:
            for tag in self.osm_tags.get(category, []):
                key, value = tag.split("=", 1)
                values = by_key.setdefault(key, [])
                if value not in values:
                    values.append(value)
        if not by_key:
            return ""

        selectors: List[str] = []
        for key in sorted(by_key):
            values = by_key[key]
            if len(values) == 1:
                selectors.append(f'node["{key}"="{values[0]}"]({area_filter});')
                selectors.append(f'way["{key}"="{values[0]}"]({area_filter});')
            else:
                pattern = "^(" + "|".join(re.escape(v) for v in values) + ")$"
                selectors.append(f'node["{key}"~"{pattern}"]({area_filter});')
                selectors.append(f'way["{key}"~"{pattern}"]({area_filter});')
        body = "\n  ".join(selectors)
        return f"[out:json][timeout:{self._server_timeout_tag()}];\n(\n  {body}\n);\nout center tags;"

    # ------------------------------------------------------------------ #
    # Network access
    # ------------------------------------------------------------------ #
    def _request_overpass(
        self,
        query: str,
        deadline: Optional[float] = None,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Send one Overpass query, failing over between mirror instances.

        Returns ``(payload, failure_kind)``. ``failure_kind`` is ``""`` on
        success, otherwise one of ``"rate_limited"`` / ``"capacity"`` /
        ``"timeout"`` / ``"budget"`` / ``"error"``.

        PHASE_30 (measured): a busy instance answers HTTP 429 / 502 / 504 and
        says so in the body ("currently at capacity. All query workers are busy
        and the request queue is full"). Those are capacity signals, so the
        next mirror is tried immediately instead of burning retries on the same
        congested host.
        """
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        last_err = "unknown error"
        kinds: List[str] = []
        attempts: List[str] = []

        for endpoint in self.base_urls[: self.max_endpoints]:
            for attempt in range(self.max_retries + 1):
                if deadline is not None and time.monotonic() > deadline:
                    return None, "budget"
                # Never let one slow mirror outlive the caller's budget: a
                # 90 s per-request timeout multiplied by several mirrors plus
                # the per-category fallback used to take minutes, so the UI
                # gave up before the honest answer arrived.
                timeout_s = self.timeout_seconds
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None, "budget"
                    timeout_s = min(timeout_s, remaining)
                started = time.monotonic()
                outcome = "ok"
                try:
                    req = urllib.request.Request(
                        endpoint,
                        data=data,
                        headers={"User-Agent": "SafeRouteAI/1.0 (PHASE_29)"},
                    )
                    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                        payload = json.loads(resp.read().decode("utf-8"))
                    attempts.append(
                        f"{_host_of(endpoint)}#{attempt} ok {time.monotonic() - started:.1f}s"
                    )
                    return payload, ""
                except urllib.error.HTTPError as e:
                    outcome = f"http{e.code}"
                    attempts.append(
                        f"{_host_of(endpoint)}#{attempt} {outcome} "
                        f"{time.monotonic() - started:.1f}s"
                    )
                    if e.code == 429:
                        kinds.append("rate_limited")
                        break  # rate limiting is endpoint-wide: try the next mirror
                    if e.code in (502, 503, 504):
                        kinds.append("capacity")
                        break  # the instance is at capacity: try the next mirror
                    last_err = f"HTTP {e.code}"
                    break  # the query itself was refused: try the next mirror
                except (socket.timeout, TimeoutError):
                    outcome = "timeout"
                    last_err = "request timed out"
                    kinds.append("timeout")
                except urllib.error.URLError as e:
                    reason = getattr(e, "reason", e)
                    if isinstance(reason, (socket.timeout, TimeoutError)) or \
                            "timed out" in str(reason).lower():
                        outcome = "timeout"
                        last_err = "request timed out"
                        kinds.append("timeout")
                    else:
                        outcome = "urlerror"
                        last_err = f"URLError: {reason}"
                        break  # the host is unreachable: try the next mirror
                except Exception as e:  # JSON / unexpected
                    outcome = type(e).__name__
                    last_err = f"{type(e).__name__}: {e}"
                attempts.append(
                    f"{_host_of(endpoint)}#{attempt} {outcome} "
                    f"{time.monotonic() - started:.1f}s"
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff_factor_seconds * (2 ** attempt))

        print(
            f"[facilities] overpass failed after {len(attempts)} attempt(s): "
            + ", ".join(attempts)
            + f" | last_error={last_err}",
            file=sys.stderr,
            flush=True,
        )
        if "rate_limited" in kinds:
            return None, "rate_limited"
        if "capacity" in kinds:
            return None, "capacity"
        if "timeout" in kinds:
            return None, "timeout"
        return None, "error"

    def _fetch_category(
        self,
        category: str,
        area_filter: str,
        deadline: Optional[float] = None,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Fetch one category. Returns ``(payload, failure_kind)``.

        ``failure_kind`` is ``""`` on success, otherwise one of
        ``"rate_limited"`` / ``"capacity"`` / ``"timeout"`` / ``"budget"`` /
        ``"error"``.
        """
        query = self._category_query(category, area_filter)
        if not query:
            return None, "error"
        return self._request_overpass(query, deadline)

    def _fetch_combined(
        self,
        categories: List[str],
        area_filter: str,
        deadline: Optional[float] = None,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Fetch every requested category in ONE request."""
        query = self._combined_query(categories, area_filter)
        if not query:
            return None, "error"
        return self._request_overpass(query, deadline)

    def _run_category_queries(
        self,
        categories: List[str],
        area_filter: str,
    ) -> Tuple[List[Dict[str, Any]], List[str], Optional[str]]:
        """Query every category. Returns ``(elements, limitations, failure_kind)``.

        ``failure_kind`` is ``None`` when at least one category succeeded.

        PHASE_30: one combined request is tried FIRST because the public
        Overpass instances are queue-bound — a single request carrying every
        category is answered in seconds, while one request per category needs
        six round trips of 30-60 s each and exhausts the lookup budget. The
        per-category path remains as the fallback, and an empty combined
        answer is re-checked per category so that a silent selector failure can
        never be reported as "there are no facilities here" (Rule 20).
        """
        elements: List[Dict[str, Any]] = []
        limitations: List[str] = []
        failures: List[str] = []
        kinds: List[str] = []
        queried = 0
        succeeded = 0
        started = time.monotonic()
        deadline = (started + self.query_deadline_seconds) if self.query_deadline_seconds > 0 else None

        combined_payload, combined_failure = self._fetch_combined(categories, area_filter, deadline)
        if combined_payload is not None:
            combined_elements = combined_payload.get("elements", []) or []
            if combined_elements:
                return combined_elements, limitations, None
            # An empty combined answer is not trusted on its own: the
            # per-category path below re-checks it.
        else:
            kinds.append(combined_failure)

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
            elif "capacity" in kinds:
                kind = "capacity"
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
            "capacity": FacilityStatus.RATE_LIMITED,
            "timeout": FacilityStatus.PROVIDER_TIMEOUT,
        }.get(failure, FacilityStatus.PROVIDER_ERROR)
        message = {
            "rate_limited": "The facility data provider rate-limited the request.",
            "capacity": (
                "The facility data provider was at capacity and could not answer "
                "the request."
            ),
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
