"""SafeRoute AI — Nominatim (OpenStreetMap) geocoding provider.

Keyless, free, no API key. Nominatim's usage policy requires a descriptive
User-Agent and at most one request per second, which this adapter honours with a
process-wide minimum interval and bounded retries.

Data (c) OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from src.geocoding.interfaces import GeocodingProvider
from src.geocoding.schemas import GeocodeCandidate, GeocodeResult, GeocodeStatus

FetchJson = Callable[[str, Dict[str, Any], Dict[str, str]], Any]


def _default_fetch_json(url: str, params: Dict[str, Any], headers: Dict[str, str]) -> Any:
    """Perform a GET with query params and return decoded JSON."""
    full = url
    if params:
        full = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers=headers)
    with urllib.request.urlopen(req, timeout=float(params.get("_timeout", 10.0))) as resp:
        return json.loads(resp.read().decode("utf-8"))


class NominatimGeocoder(GeocodingProvider):
    """Forward/reverse geocoding via the public Nominatim API."""

    _lock = threading.Lock()
    _last_call_monotonic = 0.0
    _min_interval_seconds = 1.0  # Nominatim policy: <= 1 request / second

    def __init__(
        self,
        base_url: str = "https://nominatim.openstreetmap.org",
        user_agent: str = "SafeRouteAI/1.0 (road-safety research)",
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        backoff_factor: float = 1.0,
        country_codes: str = "",
        fetch_json: Optional[FetchJson] = None,
        min_interval_seconds: Optional[float] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout = float(timeout_seconds)
        self.max_retries = int(max_retries)
        self.backoff_factor = float(backoff_factor)
        self.country_codes = country_codes or ""
        self._fetch_json = fetch_json or _default_fetch_json
        if min_interval_seconds is not None:
            self._min_interval_seconds = float(min_interval_seconds)

    @property
    def provider_name(self) -> str:
        return "nominatim"

    def _throttle(self) -> None:
        with NominatimGeocoder._lock:
            now = time.monotonic()
            wait = self._min_interval_seconds - (now - NominatimGeocoder._last_call_monotonic)
            if wait > 0:
                time.sleep(wait)
            NominatimGeocoder._last_call_monotonic = time.monotonic()

    def _request(self, path: str, params: Dict[str, Any]) -> tuple[Optional[Any], GeocodeStatus, Optional[str]]:
        url = f"{self.base_url}{path}"
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        params = dict(params)
        params["format"] = "jsonv2"
        params["_timeout"] = self.timeout
        last_err = ""
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                data = self._fetch_json(url, params, headers)
                return data, GeocodeStatus.OK, None
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    return None, GeocodeStatus.RATE_LIMITED, "Nominatim rate limit (HTTP 429)."
                last_err = f"HTTP {e.code}: {e.reason}"
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = f"network error: {e}"
            except Exception as e:  # JSON / unexpected
                last_err = f"{type(e).__name__}: {e}"
            if attempt < self.max_retries:
                time.sleep(self.backoff_factor * attempt)
        status = GeocodeStatus.PROVIDER_TIMEOUT if "tim" in last_err.lower() else GeocodeStatus.PROVIDER_ERROR
        return None, status, f"Nominatim request failed after {self.max_retries} attempts ({last_err})."

    def geocode(self, query: str, limit: int = 5) -> GeocodeResult:
        now = datetime.now(timezone.utc).isoformat()
        q = (query or "").strip()
        if not q:
            return GeocodeResult(
                status=GeocodeStatus.INVALID_REQUEST, provider=self.provider_name, query=query,
                retrieved_at=now, error_message="Empty geocoding query.",
            )

        params: Dict[str, Any] = {"q": q, "limit": max(1, min(10, int(limit)))}
        if self.country_codes:
            params["countrycodes"] = self.country_codes

        data, status, err = self._request("/search", params)
        if status != GeocodeStatus.OK or data is None:
            return GeocodeResult(status=status, provider=self.provider_name, query=q,
                                 retrieved_at=now, error_message=err)

        candidates: List[GeocodeCandidate] = []
        for item in data if isinstance(data, list) else []:
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            bb = item.get("boundingbox")
            bbox = None
            if isinstance(bb, (list, tuple)) and len(bb) == 4:
                try:
                    south, north, west, east = (float(x) for x in bb)
                    bbox = (south, north, west, east)
                except (TypeError, ValueError):
                    bbox = None
            imp = item.get("importance")
            candidates.append(GeocodeCandidate(
                display_name=str(item.get("display_name", q)),
                latitude=lat, longitude=lon, provider=self.provider_name,
                importance=float(imp) if isinstance(imp, (int, float)) else None,
                bbox=bbox,
            ))

        if not candidates:
            return GeocodeResult(status=GeocodeStatus.NO_RESULTS, provider=self.provider_name,
                                 query=q, retrieved_at=now,
                                 error_message="No matching place found.")
        return GeocodeResult(status=GeocodeStatus.OK, provider=self.provider_name, query=q,
                             candidates=candidates, retrieved_at=now)

    def reverse(self, latitude: float, longitude: float) -> GeocodeResult:
        now = datetime.now(timezone.utc).isoformat()
        params: Dict[str, Any] = {"lat": latitude, "lon": longitude}
        data, status, err = self._request("/reverse", params)
        if status != GeocodeStatus.OK or not isinstance(data, dict):
            return GeocodeResult(status=status, provider=self.provider_name,
                                 query=f"{latitude},{longitude}", retrieved_at=now, error_message=err)
        try:
            lat = float(data["lat"])
            lon = float(data["lon"])
        except (KeyError, TypeError, ValueError):
            return GeocodeResult(status=GeocodeStatus.NO_RESULTS, provider=self.provider_name,
                                 query=f"{latitude},{longitude}", retrieved_at=now,
                                 error_message="Reverse geocoding returned no usable coordinates.")
        cand = GeocodeCandidate(
            display_name=str(data.get("display_name", f"{latitude},{longitude}")),
            latitude=lat, longitude=lon, provider=self.provider_name,
        )
        return GeocodeResult(status=GeocodeStatus.OK, provider=self.provider_name,
                             query=cand.display_name, candidates=[cand], retrieved_at=now)
