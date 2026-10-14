"""SafeRoute AI — unit tests for geocoding (hermetic; fake transport)."""

import unittest

from src.geocoding.factory import create_geocoding_provider
from src.geocoding.mock_geocoder import MockGeocoder
from src.geocoding.nominatim import NominatimGeocoder
from src.geocoding.schemas import GeocodeStatus


class _FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, url, params, headers):
        self.calls.append((url, dict(params), dict(headers)))
        return self.payload


NOMINATIM_RESPONSE = [
    {"lat": "12.9756", "lon": "77.6068", "importance": 0.71,
     "display_name": "MG Road, Bengaluru, Karnataka, India",
     "boundingbox": ["12.97", "12.98", "77.60", "77.61"]},
    {"lat": "12.9716", "lon": "77.5946", "display_name": "Bengaluru, India"},
]


class TestNominatimGeocoder(unittest.TestCase):
    def test_forward_geocode_parses_candidates(self):
        t = _FakeTransport(NOMINATIM_RESPONSE)
        g = NominatimGeocoder(fetch_json=t, min_interval_seconds=0.0)
        res = g.geocode("MG Road, Bengaluru", limit=5)
        self.assertEqual(res.status, GeocodeStatus.OK)
        self.assertEqual(len(res.candidates), 2)
        self.assertAlmostEqual(res.candidates[0].latitude, 12.9756, places=3)
        self.assertEqual(res.candidates[0].provider, "nominatim")
        self.assertIsNotNone(res.candidates[0].bbox)
        self.assertTrue(t.calls[0][2].get("User-Agent"))

    def test_empty_query_rejected_without_network(self):
        t = _FakeTransport(NOMINATIM_RESPONSE)
        g = NominatimGeocoder(fetch_json=t, min_interval_seconds=0.0)
        res = g.geocode("   ")
        self.assertEqual(res.status, GeocodeStatus.INVALID_REQUEST)
        self.assertEqual(t.calls, [])

    def test_no_results(self):
        g = NominatimGeocoder(fetch_json=_FakeTransport([]), min_interval_seconds=0.0)
        self.assertEqual(g.geocode("nowhere").status, GeocodeStatus.NO_RESULTS)

    def test_reverse_geocode(self):
        payload = {"lat": "12.9716", "lon": "77.5946", "display_name": "Bengaluru, India"}
        g = NominatimGeocoder(fetch_json=_FakeTransport(payload), min_interval_seconds=0.0)
        res = g.reverse(12.9716, 77.5946)
        self.assertEqual(res.status, GeocodeStatus.OK)
        self.assertEqual(res.candidates[0].display_name, "Bengaluru, India")


class TestMockGeocoderAndFactory(unittest.TestCase):
    def test_mock_gazetteer(self):
        g = MockGeocoder()
        res = g.geocode("MG Road")
        self.assertEqual(res.status, GeocodeStatus.OK)
        self.assertTrue(res.candidates)
        self.assertEqual(g.geocode("zzz unknown").status, GeocodeStatus.NO_RESULTS)

    def test_factory_types(self):
        self.assertIsInstance(create_geocoding_provider("mock"), MockGeocoder)
        self.assertIsInstance(create_geocoding_provider("nominatim"), NominatimGeocoder)


if __name__ == "__main__":
    unittest.main()
