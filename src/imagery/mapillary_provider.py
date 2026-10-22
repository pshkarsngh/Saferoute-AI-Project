"""SafeRoute AI — Mapillary street-level imagery provider (Rule 8, Rule 9).

Retrieves real road imagery from Mapillary (CC-BY-SA 4.0) when an access token is
present. Only images spatially matched to the segment (within a documented
buffer) are used; images are downloaded ONCE into the workspace and cached.

Honesty guarantees:
- No token -> the caller-supplied fallback is used (if any) and the substitution
  is disclosed as a limitation; if there is no fallback the segment is reported as
  explicitly unavailable.
- HTTP 401/403 (auth failure) -> an explicit ``INACCESSIBLE`` result is returned.
  Geographically unrelated sample imagery is NEVER substituted for a rejected
  live request (PHASE_23B).
- No imagery within the buffer -> ``UNMATCHED`` (never treated as a safe road).
- Downloaded images stay strictly inside the workspace (Rule 1).

Mapillary imagery is (c) Mapillary contributors, CC-BY-SA 4.0.
"""

from __future__ import annotations

import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.imagery.interfaces import ImageryProvider
from src.imagery.matcher import point_to_segment_distance_m
from src.imagery.schemas import (
    ImageRef,
    ImageryResult,
    ImageryStatus,
    ImageryUnavailable,
)
from src.imagery.staleness import StalenessEvaluator
from src.routing.schemas import RouteSegment

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORAGE_REL = Path("data/imagery/mapillary")

# Mapillary's /images?bbox= endpoint returns a NON-DETERMINISTIC, arbitrary subset
# when ``limit`` is small (verified live: the same bbox returned 5/8/5 items and a
# newest capture date flipping between 2017-12-13 and 2025-07-26 at limit=12; it
# only converges to the stable, complete set at limit>=200). Requesting the
# documented maximum (2000) makes the within-buffer candidate set complete and
# deterministic so the nearest/freshest frame is never silently discarded.
# (Mapillary API v4 reference: `limit` max/default is 2000.)
CANDIDATE_LIMIT = 2000


class MapillaryHttp:
    """Thin urllib wrapper (injectable for offline tests)."""

    def __init__(self, timeout_seconds: float = 15.0, user_agent: str = "SafeRouteAI/1.0"):
        self.timeout = float(timeout_seconds)
        self.user_agent = user_agent

    def get_json(self, url: str, params: Dict[str, Any]) -> Any:
        full = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(full, headers={
            "User-Agent": self.user_agent, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def download(self, url: str, dest: Path, token: str = "") -> bool:
        headers = {"User-Agent": self.user_agent}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
        except urllib.error.HTTPError as e:
            # Signed thumbnail URLs occasionally need the token appended.
            if e.code in (401, 403) and token:
                sep = "&" if "?" in url else "?"
                req = urllib.request.Request(f"{url}{sep}access_token={token}", headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = resp.read()
            else:
                raise
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest.stat().st_size > 0


def _bbox_for_coords(coords: List[Tuple[float, float]], buffer_m: float) -> str:
    """Return 'minLon,minLat,maxLon,maxLat' covering coords + buffer (degrees)."""
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    lat_mid = sum(lats) / max(1, len(lats))
    lat_pad = buffer_m / 111320.0
    lon_pad = buffer_m / max(1.0, 111320.0 * math.cos(math.radians(lat_mid)))
    return f"{min(lons) - lon_pad:.7f},{min(lats) - lat_pad:.7f},{max(lons) + lon_pad:.7f},{max(lats) + lat_pad:.7f}"


class MapillaryImageryProvider(ImageryProvider):
    """Mapillary-backed permitted imagery provider with offline fallback."""

    source_name = "mapillary"
    licence = "CC-BY-SA 4.0"

    def __init__(
        self,
        token: str = "",
        base_url: str = "https://graph.mapillary.com",
        storage_dir: Optional[Path] = None,
        max_images: int = 3,
        search_radius_m: float = 25.0,
        thumbnail_width: int = 1024,
        download_thumbnails: bool = True,
        candidate_limit: int = CANDIDATE_LIMIT,
        staleness_max_age_days: int = 180,
        http: Optional[MapillaryHttp] = None,
        fallback: Optional[ImageryProvider] = None,
        is_source_permitted: Optional[Callable[[str], Tuple[bool, str, str]]] = None,
    ):
        self.token = token or ""
        self.base_url = base_url.rstrip("/")
        self.storage_dir = Path(storage_dir) if storage_dir else (WORKSPACE_ROOT / DEFAULT_STORAGE_REL)
        self.max_images = int(max_images)
        self.radius_m = float(search_radius_m)
        self.thumbnail_width = int(thumbnail_width)
        self.download_thumbnails = bool(download_thumbnails)
        self.candidate_limit = max(1, int(candidate_limit))
        self.http = http or MapillaryHttp()
        self.fallback = fallback
        self.staleness = StalenessEvaluator(max_age_days=staleness_max_age_days)
        self._is_source_permitted = is_source_permitted
        # thumb_1024_url / thumb_2048_url are the commonly exposed variants.
        self.thumb_field = f"thumb_{self.thumbnail_width}_url"

        # PHASE_31: identical segment bboxes are queried again by later analyses
        # of the same corridor (and by alternative routes sharing a road).
        # Mapillary frames are historical captures, not live traffic, so the
        # resolved candidate set for an identical query is reused for a bounded
        # window. Only successful responses are cached (a provider failure is
        # never masked, Rule 20), and the key covers every parameter that can
        # change the result. The access token is fingerprinted, never stored.
        self.SEARCH_CACHE_TTL_SECONDS = 3600.0
        self.SEARCH_CACHE_MAX_ENTRIES = 512
        self._search_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self._search_cache_lock = threading.Lock()
        self._token_tag = (
            hashlib.sha256(self.token.encode("utf-8")).hexdigest()[:12]
            if self.token else "no-token"
        )

    @property
    def provider_name(self) -> str:
        return "mapillary"

    # ------------------------------------------------------------------ #
    def _permitted(self, source: str) -> Tuple[bool, str, str]:
        if self._is_source_permitted is not None:
            return self._is_source_permitted(source)
        # Fallback policy: only the documented Mapillary source is allowed here.
        if source == self.source_name:
            return True, self.licence, "Permitted (CC-BY-SA 4.0)."
        return False, "UNKNOWN", f"Source '{source}' is not the Mapillary permitted source."

    def _fallback_result(self, segment: RouteSegment, note: str) -> ImageryResult:
        if self.fallback is not None:
            res = self.fallback.get_imagery_for_segment(segment)
            res.limitations = list(res.limitations) + [note]
            return res
        unavail = ImageryUnavailable(
            segment_id=segment.segment_id, reason=ImageryStatus.MISSING,
            message=note, limitations=[note, "missing_imagery_not_safe"])
        return ImageryResult(segment_id=segment.segment_id, status=ImageryStatus.MISSING,
                             images=[], unavailable_detail=unavail,
                             source=self.source_name, licence=self.licence,
                             limitations=unavail.limitations)

    def _redact(self, text: str) -> str:
        """Never allow the access token to appear in any surfaced message (Rule 13)."""
        if self.token and self.token in text:
            text = text.replace(self.token, "***")
        return text

    def _unavailable(self, segment: RouteSegment, reason: ImageryStatus, msg: str, lim: List[str]) -> ImageryResult:
        unavail = ImageryUnavailable(segment_id=segment.segment_id, reason=reason, message=msg, limitations=lim)
        return ImageryResult(segment_id=segment.segment_id, status=reason, images=[],
                             unavailable_detail=unavail, source=self.source_name,
                             licence=self.licence, limitations=list(lim))

    # ------------------------------------------------------------------ #
    def _search_candidates(self, bbox: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return the Mapillary candidate list for ``bbox``, reusing a fresh hit.

        The cache key covers the endpoint, fields, limit, radius, token identity
        and bbox, i.e. everything that determines the query result. A miss runs
        the real request and caches only a successful response.
        """
        key = "|".join([
            self.base_url, self.thumb_field, str(self.candidate_limit),
            f"{self.radius_m:.3f}", self._token_tag, bbox,
        ])
        now = time.monotonic()
        with self._search_cache_lock:
            hit = self._search_cache.get(key)
            if hit is not None and now - hit[0] < self.SEARCH_CACHE_TTL_SECONDS:
                return hit[1]

        payload = self.http.get_json(f"{self.base_url}/images", params)
        items = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            items = []

        with self._search_cache_lock:
            if len(self._search_cache) >= self.SEARCH_CACHE_MAX_ENTRIES:
                expired = [k for k, (ts, _) in self._search_cache.items()
                           if now - ts >= self.SEARCH_CACHE_TTL_SECONDS]
                for k in expired:
                    self._search_cache.pop(k, None)
                while len(self._search_cache) >= self.SEARCH_CACHE_MAX_ENTRIES:
                    oldest = min(self._search_cache.items(), key=lambda kv: kv[1][0])[0]
                    self._search_cache.pop(oldest, None)
            self._search_cache[key] = (now, items)
        return items

    # ------------------------------------------------------------------ #
    def get_imagery_for_segment(
        self,
        segment: RouteSegment,
        permitted_source: Optional[str] = None,
    ) -> ImageryResult:
        source = permitted_source or self.source_name
        allowed, licence, reason = self._permitted(source)
        if not allowed:
            return self._unavailable(
                segment, ImageryStatus.DISALLOWED_SOURCE, reason,
                [f"disallowed_imagery_source_{source}", "missing_imagery_not_safe"])

        if not self.token:
            return self._fallback_result(
                segment, "live_mapillary_disabled_no_token_using_local_archive")

        coords = segment.geometry.coordinates
        if not coords:
            return self._unavailable(segment, ImageryStatus.UNMATCHED,
                                     "Segment has no geometry to match imagery against.",
                                     ["unmatched_segment_imagery", "missing_imagery_not_safe"])

        bbox = _bbox_for_coords(coords, self.radius_m)
        params = {
            "access_token": self.token,
            "fields": f"id,captured_at,compass_angle,geometry,{self.thumb_field}",
            "bbox": bbox,
            # A large limit is REQUIRED for correctness: small limits return a
            # non-deterministic, incomplete subset (see CANDIDATE_LIMIT note).
            "limit": self.candidate_limit,
        }

        try:
            items = self._search_candidates(bbox, params)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                # PHASE_23B: authentication failure must NEVER silently substitute
                # geographically unrelated sample imagery. Return an explicit,
                # disclosed INACCESSIBLE result instead (Rule 9).
                return self._unavailable(
                    segment, ImageryStatus.INACCESSIBLE,
                    self._redact(
                        f"Mapillary authentication failed (HTTP {e.code}); the access "
                        f"token was rejected or lacks permission. No imagery was "
                        f"substituted."),
                    ["mapillary_auth_failed", "mapillary_auth_failed_no_substitution",
                     "missing_imagery_not_safe"])
            if e.code == 429:
                return self._unavailable(segment, ImageryStatus.INACCESSIBLE,
                                         "Mapillary rate limit (HTTP 429).", ["mapillary_rate_limited"])
            return self._unavailable(segment, ImageryStatus.INACCESSIBLE,
                                     self._redact(f"Mapillary HTTP error {e.code}."),
                                     ["mapillary_provider_error"])
        except Exception as e:
            return self._unavailable(
                segment, ImageryStatus.INACCESSIBLE,
                self._redact(f"Mapillary request failed: {type(e).__name__}: {e}"),
                ["mapillary_provider_error"])

        ranked: List[Tuple[Dict[str, Any], float]] = []
        for item in items:
            geom = item.get("geometry") or {}
            point = geom.get("coordinates") if isinstance(geom, dict) else None
            if not point or len(point) < 2:
                continue
            dist = point_to_segment_distance_m((float(point[0]), float(point[1])), coords)
            if dist <= self.radius_m:
                ranked.append((item, dist))

        if not ranked:
            return self._unavailable(
                segment, ImageryStatus.UNMATCHED,
                f"No Mapillary imagery within {self.radius_m:.0f} m of segment geometry.",
                ["unmatched_segment_imagery", "missing_imagery_not_safe"])

        # Evaluate freshness for EVERY in-buffer candidate, then prefer fresh
        # imagery (Rule 9): a fresh frame must never be displaced by a nearer
        # stale frame. Only when no fresh frame exists do we fall back to the
        # stale frames (which keeps the existing stale-evidence scoring path).
        # The 180-day freshness policy itself is unchanged (StalenessEvaluator).
        evaluated = []
        for item, dist in ranked:
            captured_at = self._epoch_to_iso(item.get("captured_at"))
            is_stale, _age, note = self.staleness.evaluate(captured_at)
            evaluated.append((item, dist, captured_at, is_stale, note))

        fresh = [e for e in evaluated if not e[3]]
        pool = fresh if fresh else evaluated
        pool.sort(key=lambda e: e[1])
        pool = pool[: self.max_images]

        now_iso = datetime.now(timezone.utc).isoformat()
        image_refs: List[ImageRef] = []
        limitations: List[str] = []
        has_stale = False
        for item, dist, captured_at, is_stale, note in pool:
            mid = str(item.get("id", "unknown"))
            if is_stale:
                has_stale = True
                if note:
                    limitations.append(note)

            file_path = ""
            status_str = "stale" if is_stale else "available"
            if self.download_thumbnails:
                thumb = item.get(self.thumb_field)
                if not thumb:
                    limitations.append(f"mapillary_image_{mid}_has_no_thumbnail")
                    continue
                dest = self.storage_dir / f"{mid}.jpg"
                try:
                    if not (dest.is_file() and dest.stat().st_size > 0):
                        self.http.download(thumb, dest, token=self.token)
                    file_path = str(dest)
                except Exception:
                    limitations.append(f"mapillary_image_{mid}_download_failed")
                    continue

            point = item.get("geometry", {}).get("coordinates", [None, None])
            image_refs.append(ImageRef(
                image_id=f"mapillary_{mid}",
                file_path=file_path,
                source=self.source_name,
                licence=licence,
                retrieved_at=now_iso,
                captured_at=captured_at,
                coordinates=(float(point[0]), float(point[1])) if point and None not in point else None,
                distance_to_segment_m=dist,
                is_stale=is_stale,
                status=status_str,
            ))

        if not image_refs:
            return self._unavailable(
                segment, ImageryStatus.INACCESSIBLE,
                "Mapillary imagery was found but none could be downloaded.",
                ["mapillary_download_failed", "missing_imagery_not_safe"])

        overall = ImageryStatus.STALE if has_stale else ImageryStatus.AVAILABLE
        return ImageryResult(segment_id=segment.segment_id, status=overall, images=image_refs,
                             source=self.source_name, licence=licence, limitations=limitations)

    @staticmethod
    def _epoch_to_iso(value: Any) -> Optional[str]:
        if value is None:
            return None
        try:
            # Mapillary returns captured_at in milliseconds since epoch.
            ts = float(value)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return None
