"""SafeRoute AI — Mapillary provider unit tests (hermetic, no network)."""

import time
import unittest
import tempfile
from pathlib import Path

from src.imagery.mapillary_provider import MapillaryImageryProvider
from src.imagery.schemas import ImageryResult, ImageryStatus
from src.routing.schemas import Coordinate, RouteGeometry, RouteSegment

TMP = Path(__file__).resolve().parent.parent.parent / "data" / "imagery" / "_test_mapillary"

_DAY_MS = 86_400_000
_NOW_MS = int(time.time() * 1000)
FRESH_MS = _NOW_MS - 10 * _DAY_MS     # well inside the 180-day policy window
STALE_MS = _NOW_MS - 400 * _DAY_MS    # beyond the policy window


class _FakeHttp:
    def __init__(self, payload=None, fail=False):
        self.payload = payload or {"data": []}
        self.fail = fail
        self.downloads = []
        self.last_params = {}
        self.params_history = []

    def get_json(self, url, params):
        self.last_params = dict(params)
        self.params_history.append(dict(params))
        return self.payload

    def download(self, url, dest, token=""):
        self.downloads.append(str(dest))
        if self.fail:
            raise RuntimeError("boom")
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"\xff\xd8\xff\xe0fake")
        return True


def _segment():
    return RouteSegment(
        segment_id="seg-t-0000", route_id="route-t", sequence=0, length_m=200.0,
        duration_s=20.0, start_coord=Coordinate(12.9716, 77.5946),
        end_coord=Coordinate(12.9726, 77.5956),
        geometry=RouteGeometry(coordinates=[(77.5946, 12.9716), (77.5956, 12.9726)]),
    )


def _payload(within=True):
    lon, lat = (77.59465, 12.97165) if within else (78.5, 13.5)
    return {"data": [{
        "id": "12345", "captured_at": 1735689600000,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "thumb_1024_url": "https://example.invalid/12345.jpg",
    }]}


def _img(mid, lat, lon, captured_ms, thumb=None):
    return {
        "id": mid, "captured_at": captured_ms,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "thumb_1024_url": thumb or f"https://example.invalid/{mid}.jpg",
    }


def _provider(http, token="tok", fallback=None):
    return MapillaryImageryProvider(
        token=token, http=http, download_thumbnails=True,
        storage_dir=Path(tempfile.mkdtemp(prefix="sr_map_")), search_radius_m=25.0,
        fallback=fallback)


class _Fallback:
    provider_name = "workspace"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        return ImageryResult(segment_id=segment.segment_id, status=ImageryStatus.MISSING,
                             images=[], limitations=["missing_imagery_not_safe"])


class TestMapillaryProvider(unittest.TestCase):
    def test_no_token_uses_fallback_and_discloses(self):
        p = _provider(_FakeHttp(), token="", fallback=_Fallback())
        res = p.get_imagery_for_segment(_segment())
        self.assertEqual(res.status, ImageryStatus.MISSING)
        self.assertTrue(any("live_mapillary_disabled" in l for l in res.limitations))

    def test_no_token_without_fallback_is_unavailable(self):
        res = _provider(_FakeHttp(), token="").get_imagery_for_segment(_segment())
        self.assertEqual(res.status, ImageryStatus.MISSING)
        self.assertIn("missing_imagery_not_safe", res.limitations)

    def test_matched_image_downloads_and_records_provenance(self):
        http = _FakeHttp(_payload(within=True))
        res = _provider(http).get_imagery_for_segment(_segment())
        self.assertIn(res.status, [ImageryStatus.AVAILABLE, ImageryStatus.STALE])
        self.assertEqual(len(res.images), 1)
        img = res.images[0]
        self.assertEqual(img.source, "mapillary")
        self.assertEqual(img.licence, "CC-BY-SA 4.0")
        self.assertTrue(img.file_path)
        self.assertEqual(len(http.downloads), 1)

    def test_far_image_is_unmatched(self):
        res = _provider(_FakeHttp(_payload(within=False))).get_imagery_for_segment(_segment())
        self.assertEqual(res.status, ImageryStatus.UNMATCHED)
        self.assertEqual(res.images, [])

    def test_download_failure_is_inaccessible(self):
        res = _provider(_FakeHttp(_payload(within=True), fail=True)).get_imagery_for_segment(_segment())
        self.assertEqual(res.status, ImageryStatus.INACCESSIBLE)

    def test_disallowed_source_rejected(self):
        def policy(src):
            return (False, "PROPRIETARY", "disallowed")
        p = MapillaryImageryProvider(token="tok", http=_FakeHttp(), is_source_permitted=policy)
        res = p.get_imagery_for_segment(_segment(), permitted_source="google_street_view")
        self.assertEqual(res.status, ImageryStatus.DISALLOWED_SOURCE)

    # ---- PHASE_26: imagery-acquisition reliability ------------------------- #

    def test_requests_full_candidate_set(self):
        """The bbox query is non-deterministic for small `limit` values (live API
        returns a random subset that can exclude the newest frames). The provider
        must request a large candidate limit so the candidate set is complete and
        stable before selection."""
        http = _FakeHttp(_payload(within=True))
        _provider(http).get_imagery_for_segment(_segment())
        self.assertGreaterEqual(int(http.last_params.get("limit", 0)), 500)

    def test_prefers_fresh_over_nearer_stale(self):
        """A fresher frame must not be displaced by a nearer stale frame (Rule 9)."""
        stale_near = _img("stale_near", 12.9716, 77.5946, STALE_MS)   # on the segment
        fresh_far = _img("fresh_far", 12.97174, 77.5946, FRESH_MS)    # ~15 m away
        http = _FakeHttp({"data": [stale_near, fresh_far]})
        res = _provider(http).get_imagery_for_segment(_segment())
        self.assertEqual(res.status, ImageryStatus.AVAILABLE)
        self.assertEqual([i.image_id for i in res.images], ["mapillary_fresh_far"])
        self.assertFalse(res.images[0].is_stale)

    def test_stale_only_is_marked_stale(self):
        http = _FakeHttp({"data": [_img("stale_only", 12.9716, 77.5946, STALE_MS)]})
        res = _provider(http).get_imagery_for_segment(_segment())
        self.assertEqual(res.status, ImageryStatus.STALE)
        self.assertTrue(res.images[0].is_stale)

    def test_nearest_is_preferred_among_fresh(self):
        near_fresh = _img("fresh_near", 12.9716, 77.5946, FRESH_MS)
        far_fresh = _img("fresh_far2", 12.97174, 77.5946, FRESH_MS)
        http = _FakeHttp({"data": [far_fresh, near_fresh]})
        res = _provider(http).get_imagery_for_segment(_segment())
        # Both are fresh (kept, <= max_images) but ordered nearest-first.
        self.assertEqual([i.image_id for i in res.images],
                         ["mapillary_fresh_near", "mapillary_fresh_far2"])

    def test_per_call_cap_limits_downloads(self):
        """PHASE_33: long-route mode caps frames before any thumbnail download."""
        http = _FakeHttp({"data": [
            _img("fresh_a", 12.9716, 77.5946, FRESH_MS),
            _img("fresh_b", 12.9717, 77.5946, FRESH_MS),
            _img("fresh_c", 12.9718, 77.5946, FRESH_MS),
        ]})
        res = _provider(http).get_imagery_for_segment(_segment(), max_images=1)
        self.assertEqual(len(res.images), 1)
        self.assertEqual(len(http.downloads), 1)


if __name__ == "__main__":
    unittest.main()
