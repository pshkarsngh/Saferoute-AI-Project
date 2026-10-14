"""SafeRoute AI — Mapillary provider unit tests (hermetic, no network)."""

import unittest
import tempfile
from pathlib import Path

from src.imagery.mapillary_provider import MapillaryImageryProvider
from src.imagery.schemas import ImageryResult, ImageryStatus
from src.routing.schemas import Coordinate, RouteGeometry, RouteSegment

TMP = Path(__file__).resolve().parent.parent.parent / "data" / "imagery" / "_test_mapillary"


class _FakeHttp:
    def __init__(self, payload=None, fail=False):
        self.payload = payload or {"data": []}
        self.fail = fail
        self.downloads = []

    def get_json(self, url, params):
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


if __name__ == "__main__":
    unittest.main()
