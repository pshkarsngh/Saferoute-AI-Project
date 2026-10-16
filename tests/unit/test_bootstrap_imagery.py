"""SafeRoute AI — imagery provider-selection safeguard tests (hermetic, no network).

PHASE_25 regression coverage for ``src.api.bootstrap.build_imagery_provider``:

1. ``imagery_source == "mapillary"`` with a token -> the live Mapillary provider
   is selected.
2. ``imagery_source == "mapillary"`` WITHOUT a token -> a demo-capable local
   adapter is never silently selected; the Mapillary provider's established
   missing-token/unavailable path is used instead.
3. Explicit demo configuration (a non-Mapillary source + demo mode) still works.
4. The missing-token path never emits demo sample frames as route evidence.

No external network requests are made: every provider exercised here short-circuits
before any HTTP call (no token, or demo-only local archive).

Governing: master_rules.md Rules 8, 9, 14, 20.
"""

import unittest

from src.api.bootstrap import build_imagery_provider
from src.api.pipeline import SafetyAnalysisPipeline
from src.config.settings import Settings
from src.imagery.adapter import PermittedImageryAdapter
from src.imagery.mapillary_provider import MapillaryImageryProvider
from src.imagery.schemas import ImageryStatus
from src.routing.schemas import (
    Coordinate,
    Route,
    RouteGeometry,
    RouteSegment,
)

COORDS = [(77.5946, 12.9716), (77.5956, 12.9726)]


def _segment(segment_id="seg-boot-0000"):
    return RouteSegment(
        segment_id=segment_id, route_id="route-boot", sequence=0, length_m=200.0,
        duration_s=20.0, start_coord=Coordinate(12.9716, 77.5946),
        end_coord=Coordinate(12.9726, 77.5956),
        geometry=RouteGeometry(coordinates=COORDS),
    )


def _route(segment):
    return Route(
        route_id="route-boot", provider="test", summary="s", distance_m=200.0,
        duration_s=20.0, geometry=RouteGeometry(coordinates=COORDS),
        segments=[segment],
    )


class TestBootstrapImagerySelection(unittest.TestCase):
    def test_mapillary_selected_with_token_uses_mapillary_provider(self):
        settings = Settings(imagery_source="mapillary", mapillary_token="test-token")
        provider = build_imagery_provider(settings)
        self.assertIsInstance(provider, MapillaryImageryProvider)
        self.assertEqual(provider.provider_name, "mapillary")
        self.assertTrue(provider.token)

    def test_mapillary_without_token_does_not_select_demo_capable_adapter(self):
        # demo mode explicitly ON, but a Mapillary source with no token must still
        # not resolve to a demo-capable local adapter.
        settings = Settings(
            imagery_source="mapillary", mapillary_token="", imagery_demo_mode=True)
        provider = build_imagery_provider(settings)
        self.assertIsInstance(provider, MapillaryImageryProvider)
        self.assertEqual(provider.provider_name, "mapillary")
        self.assertFalse(provider.token)
        self.assertIsNotNone(provider.fallback)
        self.assertFalse(
            getattr(provider.fallback, "demo_mode", True),
            "the disclosed local-archive fallback must never be demo-capable",
        )

    def test_explicit_demo_configuration_is_preserved(self):
        settings = Settings(
            imagery_source="workspace_dashcam_v1", mapillary_token="",
            imagery_demo_mode=True)
        provider = build_imagery_provider(settings)
        self.assertIsInstance(provider, PermittedImageryAdapter)
        self.assertTrue(provider.demo_mode)

        result = provider.get_imagery_for_segment(
            _segment(), permitted_source="workspace_dashcam_v1")
        self.assertTrue(all(img.is_demo for img in result.images))
        if result.images:
            self.assertIn("demo_imagery_not_route_evidence", result.limitations)

    def test_non_demo_local_source_stays_non_demo(self):
        settings = Settings(
            imagery_source="workspace_dashcam_v1", mapillary_token="",
            imagery_demo_mode=False)
        provider = build_imagery_provider(settings)
        self.assertIsInstance(provider, PermittedImageryAdapter)
        self.assertFalse(provider.demo_mode)


class TestMissingTokenPathNeverEmitsDemoImagery(unittest.TestCase):
    def test_missing_token_yields_unavailable_without_demo_frames(self):
        # Even with demo mode explicitly ON, a Mapillary source without a token
        # must not surface demo sample frames as route evidence.
        settings = Settings(
            imagery_source="mapillary", mapillary_token="", imagery_demo_mode=True)
        provider = build_imagery_provider(settings)

        result = provider.get_imagery_for_segment(_segment())
        self.assertEqual(result.images, [])
        self.assertFalse(any(img.is_demo for img in result.images))
        self.assertFalse(result.is_available)
        self.assertIn(result.status, [ImageryStatus.MISSING, ImageryStatus.UNMATCHED])
        self.assertIn("missing_imagery_not_safe", result.limitations)
        self.assertNotIn("demo_imagery_not_route_evidence", result.limitations)

    def test_pipeline_classifies_missing_token_as_real_evidence_not_demo(self):
        # End-to-end through the pipeline: a Mapillary source without a token must
        # never be labelled as demo evidence, and must stay unassessed rather than
        # producing a recommendation from sample frames.
        settings = Settings(
            imagery_source="mapillary", mapillary_token="", imagery_demo_mode=True)
        pipeline = SafetyAnalysisPipeline(
            imagery_adapter=build_imagery_provider(settings))

        result = pipeline._analyze_route(_route(_segment()))
        self.assertEqual(result["evidence_class"], "real")
        emitted = [
            img
            for meta in result["imagery"]
            for img in (meta.get("images") or [])
        ]
        self.assertEqual(emitted, [])
        self.assertFalse(any(img.get("is_demo") for img in emitted))


if __name__ == "__main__":
    unittest.main()
