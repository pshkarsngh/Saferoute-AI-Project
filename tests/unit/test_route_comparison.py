"""SafeRoute AI — Deterministic Route Comparison & Recommendation tests (PHASE_25).

Controlled, known route-risk inputs verify:
- safest sufficiently assessed route selection;
- per-route ranking reasons (why higher / why lower) and distance/time deltas;
- insufficient coverage, ties, all-unassessed, single-route and demo-evidence cases;
- determinism of the comparison output.

Governing rules: master_rules.md Rules 7, 9, 10, 12, 14, 20.
"""

import json
import unittest

from src.risk.comparison import RouteComparer, assessed_length_fraction, load_comparison_policy


def _seg(i, length_m, score):
    return {"segment_id": f"seg-{i}", "length_m": length_m, "segment_score": score}


def _route(route_id, score, hazards=(), distance_m=5000.0, duration_s=600.0,
           status="assessed", evidence_class="real", segment_scores=None,
           detection_outcome="hazards_detected"):
    segs = segment_scores if segment_scores is not None else [
        _seg(1, 1000.0, score), _seg(2, 1000.0, score)
    ]
    return {
        "route_id": route_id,
        "route_score": score,
        "status": status,
        "evidence_class": evidence_class,
        "distance_m": distance_m,
        "duration_s": duration_s,
        "hazards_total": len(hazards),
        "hazards": list(hazards),
        "detection_outcome": detection_outcome,
        "coverage": {"images_total": 4, "images_used": 4, "fraction": 1.0},
        "segment_scores": segs,
    }


class TestRouteComparer(unittest.TestCase):
    def setUp(self):
        self.cmp = RouteComparer()

    # ------------------------------------------------- selection ---------- #
    def test_higher_score_is_recommended(self):
        a = _route("route_a", 88.0)
        b = _route("route_b", 71.5)
        out = self.cmp.build([a, b], assessed_at="2026-10-16T00:00:00Z")
        self.assertEqual(out["recommendation_status"], "recommended")
        self.assertEqual(out["recommended_route_id"], "route_a")
        self.assertEqual(out["comparability"], "sufficiently_assessed_comparison")
        self.assertAlmostEqual(out["score_margin_to_runner_up"], 16.5, places=2)
        self.assertEqual(out["assessed_at"], "2026-10-16T00:00:00Z")
        self.assertEqual([e["route_id"] for e in out["ranking"]], ["route_a", "route_b"])
        self.assertTrue(out["recommendation_reasons"])

    def test_ranking_reasons_explain_why_lower(self):
        a = _route("route_a", 88.0,
                   hazards=[{"hazard_class": "pothole", "segment_id": "seg-1"}],
                   distance_m=5000.0, duration_s=600.0)
        b = _route("route_b", 71.5,
                   hazards=[{"hazard_class": "crack", "segment_id": "seg-9"},
                            {"hazard_class": "crack", "segment_id": "seg-10"}],
                   distance_m=6200.0, duration_s=780.0)
        out = self.cmp.build([a, b])
        rank2 = out["ranking"][1]
        joined = " ".join(rank2["reasons"])
        self.assertIn("route_a", joined)          # why it ranks below
        self.assertIn("1 more supported hazard", joined)
        self.assertAlmostEqual(rank2["score_delta_vs_recommended"], -16.5, places=2)
        self.assertAlmostEqual(rank2["distance_delta_vs_recommended"], 1200.0, places=1)
        self.assertAlmostEqual(rank2["duration_delta_vs_recommended"], 180.0, places=1)
        self.assertEqual(rank2["hazard_segments"], ["seg-9", "seg-10"])

    def test_recommended_route_reason_mentions_comparison(self):
        a = _route("route_a", 90.0, distance_m=4000.0, duration_s=500.0)
        b = _route("route_b", 80.0, distance_m=5000.0, duration_s=650.0)
        out = self.cmp.build([a, b])
        text = " ".join(out["recommendation_reasons"])
        self.assertIn("route_b", text)
        self.assertIn("shorter", text)

    # ------------------------------------------------- edge cases --------- #
    def test_insufficient_coverage_excluded_from_recommendation(self):
        a = _route("route_a", 88.0)
        c = _route("route_c", 95.0, status="partially_assessed",
                   segment_scores=[_seg(1, 1000.0, 95.0), _seg(2, 3000.0, None)])
        out = self.cmp.build([a, c])
        # route_c has the higher raw score but only 25% assessed length.
        self.assertEqual(out["recommended_route_id"], "route_a")
        rank1 = out["ranking"][0]
        self.assertEqual(rank1["route_id"], "route_c")
        self.assertFalse(rank1["sufficiently_assessed"])
        self.assertAlmostEqual(rank1["assessed_length_fraction"], 0.25, places=4)
        self.assertTrue(any("Not eligible" in r for r in rank1["reasons"]))
        self.assertTrue(any("above the recommended route" in r for r in rank1["reasons"]))

    def test_tied_scores_yield_no_recommendation(self):
        a = _route("route_a", 80.0)
        b = _route("route_b", 80.0)
        out = self.cmp.build([a, b])
        self.assertIsNone(out["recommended_route_id"])
        self.assertEqual(out["recommendation_status"], "cannot_determine")
        self.assertEqual(out["comparability"], "tied_scores")
        self.assertEqual(set(out["tied_route_ids"]), {"route_a", "route_b"})
        self.assertIn("tied", out["cannot_determine_reason"].lower())

    def test_all_routes_unassessed_cannot_determine(self):
        a = _route("route_a", None, status="unassessed")
        b = _route("route_b", None, status="unassessed")
        out = self.cmp.build([a, b])
        self.assertIsNone(out["recommended_route_id"])
        self.assertEqual(out["ranking"], [])
        self.assertEqual(out["comparability"], "all_routes_unassessed")
        self.assertEqual(set(out["unassessed_route_ids"]), {"route_a", "route_b"})
        self.assertIn("unassessed", out["cannot_determine_reason"])

    def test_no_routes_at_all(self):
        out = self.cmp.build([])
        self.assertIsNone(out["recommended_route_id"])
        self.assertEqual(out["comparability"], "no_routes_scored")
        self.assertEqual(out["ranking"], [])

    def test_single_assessed_route_recommended_with_disclosure(self):
        a = _route("route_a", 70.0)
        b = _route("route_b", None, status="unassessed")
        out = self.cmp.build([a, b])
        self.assertEqual(out["recommended_route_id"], "route_a")
        self.assertEqual(out["comparability"], "single_sufficiently_assessed_route")
        self.assertIn("route_b", out["unassessed_route_ids"])
        reasons = " ".join(out["recommendation_reasons"])
        self.assertTrue("only 1 of" in reasons.lower() or "could not be" in reasons.lower())

    def test_demo_evidence_excluded_from_recommendation(self):
        real = _route("route_real", 70.0)
        demo = _route("route_demo", 99.0, evidence_class="demo")
        out = self.cmp.build([real, demo])
        self.assertEqual(out["recommended_route_id"], "route_real")
        demo_entry = next(e for e in out["ranking"] if e["route_id"] == "route_demo")
        self.assertEqual(demo_entry["evidence_class"], "demo")
        self.assertFalse(demo_entry["sufficiently_assessed"])
        self.assertTrue(any("demo imagery" in r.lower() for r in demo_entry["reasons"]))

    def test_demo_only_evidence_cannot_recommend(self):
        d = _route("route_demo", 99.0, evidence_class="demo")
        out = self.cmp.build([d])
        self.assertIsNone(out["recommended_route_id"])
        self.assertEqual(out["comparability"], "demo_evidence_only")
        self.assertIn("demo", out["cannot_determine_reason"].lower())

    # ------------------------------------------------- helpers/guards ----- #
    def test_assessed_length_fraction_helper(self):
        route = _route("r", 50.0, segment_scores=[_seg(1, 750.0, 50.0), _seg(2, 250.0, None)])
        self.assertAlmostEqual(assessed_length_fraction(route), 0.75, places=4)
        self.assertAlmostEqual(assessed_length_fraction({"segment_scores": []}), 0.0, places=4)

    def test_unassessed_never_ranked(self):
        a = _route("route_a", 60.0)
        b = _route("route_b", None, status="unassessed")
        out = self.cmp.build([a, b])
        self.assertNotIn("route_b", [e["route_id"] for e in out["ranking"]])
        self.assertIn("route_b", out["unassessed_route_ids"])

    def test_determinism(self):
        a = _route("route_a", 82.0)
        b = _route("route_b", 74.0)
        out1 = self.cmp.build([a, b], assessed_at="2026-10-16T00:00:00Z")
        out2 = self.cmp.build([a, b], assessed_at="2026-10-16T00:00:00Z")
        self.assertEqual(json.dumps(out1, sort_keys=True), json.dumps(out2, sort_keys=True))

    def test_policy_defaults_loaded(self):
        policy = load_comparison_policy()
        self.assertIn("recommendation", policy)
        self.assertAlmostEqual(self.cmp.min_assessed_length_fraction, 0.50, places=4)


if __name__ == "__main__":
    unittest.main()
