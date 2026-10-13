"""SafeRoute AI — OpenStreetMap (Overpass) Facilities Provider.

Phase ID: PHASE_15. Data (c) OpenStreetMap contributors, ODbL — free, no API key.
Facilities are CONTEXT ONLY and never enter the hazard score (Rule 11).
Never fabricates facilities; failures map to explicit statuses (Rule 20).
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.facilities.interfaces import FacilitiesProvider
from src.facilities.schemas import Facility, FacilityResult, FacilityStatus
from src.routing.segmentation import haversine_distance_m

DEFAULT_OSM_TAGS = {
    "hospital": "amenity=hospital",
    "pharmacy": "amenity=pharmacy",
    "police": "amenity=police",
    "fuel": "amenity=fuel",
    "hotel": "tourism=hotel",
    "restaurant": "amenity=restaurant",
}


class OverpassFacilitiesProvider(FacilitiesProvider):
    """Live facilities provider backed by the OpenStreetMap Overpass API."""

    def __init__(
        self,
        base_url: str = "https://overpass-api.de/api/interpreter",
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        backoff_factor_seconds: float = 0.5,
        osm_tags: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)
        self.backoff_factor_seconds = float(backoff_factor_seconds)
        self.osm_tags = dict(osm_tags) if osm_tags else dict(DEFAULT_OSM_TAGS)

    @property
    def provider_name(self) -> str:
        return "overpass"

    def _build_query(self, latitude: float, longitude: float, radius_m: float, categories: List[str]) -> str:
        selectors = []
        for cat in categories:
            tag = self.osm_tags.get(cat)
            if not tag:
                continue
            key, value = tag.split("=", 1)
            selectors.append(f'node["{key}"="{value}"](around:{radius_m:.0f},{latitude},{longitude});')
            selectors.append(f'way["{key}"="{value}"](around:{radius_m:.0f},{latitude},{longitude});')
        body = "\n  ".join(selectors)
        return f"[out:json][timeout:{int(self.timeout_seconds)}];\n(\n  {body}\n);\nout center tags;"

    def get_nearby_facilities(self, latitude, longitude, radius_m=None, categories=None):
        now = datetime.now(timezone.utc).isoformat()
        radius = float(radius_m if radius_m is not None else 1000.0)
        cats = list(categories) if categories else list(self.osm_tags.keys())
        base = dict(provider=self.provider_name, categories_requested=cats, radius_m=radius,
                    origin_latitude=latitude, origin_longitude=longitude, retrieved_at=now)

        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            return FacilityResult(status=FacilityStatus.INVALID_REQUEST,
                                  error_message="Invalid coordinates.", **base)

        query = self._build_query(latitude, longitude, radius, cats)
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(self.base_url, data=data,
                                             headers={"User-Agent": "SafeRouteAI/1.0 (PHASE_15)"})
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                return self._parse(payload, cats, latitude, longitude, radius, base)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    return FacilityResult(status=FacilityStatus.RATE_LIMITED,
                                          error_message="Overpass rate limit (429).", **base)
                last_err = f"HTTP {e.code}"
            except Exception as e:  # timeout / connection / JSON
                last_err = f"{type(e).__name__}: {e}"
            if attempt < self.max_retries:
                time.sleep(self.backoff_factor_seconds * (2 ** attempt))
        return FacilityResult(status=FacilityStatus.PROVIDER_ERROR,
                              error_message=f"Overpass request failed: {last_err}", **base)

    def _parse(self, payload, cats, latitude, longitude, radius, base):
        reverse = {v: k for k, v in self.osm_tags.items()}
        out: List[Facility] = []
        for el in payload.get("elements", []):
            tags = el.get("tags", {}) or {}
            cat = None
            for key in ("amenity", "tourism"):
                tag = f"{key}={tags.get(key)}"
                if tag in reverse:
                    cat = reverse[tag]
                    break
            if cat is None or cat not in cats:
                continue
            if el.get("type") == "node":
                lat, lon = el.get("lat"), el.get("lon")
            else:
                center = el.get("center", {}) or {}
                lat, lon = center.get("lat"), center.get("lon")
            if lat is None or lon is None:
                continue
            dist = haversine_distance_m((longitude, latitude), (lon, lat))
            if dist > radius:
                continue
            out.append(Facility(
                facility_id=f"osm-{el.get('type')}-{el.get('id')}",
                category=cat,
                name=tags.get("name") or f"{cat.title()} (unnamed)",
                latitude=lat, longitude=lon, distance_m=dist,
                source=self.provider_name))
        out.sort(key=lambda f: f.distance_m)
        if not out:
            return FacilityResult(status=FacilityStatus.UNAVAILABLE,
                                  limitations=["no_facilities_found_within_radius"], **base)
        return FacilityResult(status=FacilityStatus.OK, facilities=out, **base)


