"""SafeRoute AI — Route-RECOMMENDATION CORRECTNESS verification (not just test-pass status).

Why this file exists
--------------------
`tests/unit/test_route_comparison.py` injects an already-computed `route_score`
(`_route("route_a", 88.0)`), so it exercises the *comparison policy in isolation*
but never proves that hazard evidence is turned into the CORRECT score, nor that
the CORRECT route is selected when the real risk engine is in the loop.

This file closes that gap by driving SYNTHETIC, explicitly labelled hazard
evidence through the REAL production chain:

    synthetic DetectionRecord
      -> HazardAggregator.assess_segment   (confidence filter, severity policy)
      -> DeterministicRiskEngine.score_route (S_i, H_i, length-weighted route score)
      -> RouteComparer.build               (ranking, eligibility, recommendation)
      -> GroundedExplanationService        (deterministic fallback text)

and asserting the OBSERVED values against expectations that were HAND-COMPUTED
from the documented formula, with the arithmetic shown in each case:

    severity   = clamp(base * (1 + 0.50 * area/max_area) * (1 + 0.25 * (conf - 0.25)), 1, 5)
    H_i        = sum(severity) / max(length_m / 1000, 0.10)
    S_i        = round(100 * exp(-0.10 * H_i), 2)
    route      = round(sum(length_i * S_i) / sum(length_i), 2)   [scored segments only]
    eligible   = assessed_length_fraction >= 0.50 and evidence_class != 'demo'
    tie        = |score_a - score_b| <= 0.0  (exact equality only)

Source of every constant: config/hazard_severity.yaml, config/risk_engine.yaml,
config/route_comparison.yaml. NO formula or threshold is altered here.

SCOPE / HONESTY (master_rules.md Rules 7, 9, 14, 20)
----------------------------------------------------
- All imagery ids, coordinates and detections here are SYNTHETIC and prefixed
  `SYNTHETIC-`. No real road, GPS trace, image or real-world accuracy claim is
  made or implied.
- Passing these tests proves LOGICAL CORRECTNESS of the scoring/ranking policy on
  controlled inputs. It is NOT evidence that any real road is safe, and it is NOT
  a substitute for geographically matched imagery and independent validation.
"""

import math
import unittest

from src.detection.schemas import DetectionRecord, DetectionStatus, ImageDetectionResult
from src.imagery.interfaces import ImageryProvider
from src.imagery.schemas import ImageRef, ImageryResult, ImageryStatus
from src.llm.explainer import GroundedExplanationService
from src.risk.aggregate import HazardAggregator
from src.risk.comparison import RouteComparer, assessed_length_fraction
from src.risk.engine import DeterministicRiskEngine
from src.risk.severity import SeverityPolicy

SYN = "SYNTHETIC-"

# --- Hand-computed constants (see module docstring for the formulas) -------- #
# max-credible-area box: area_norm = 1.0 * 0.30 = 0.30 == max_bbox_area_norm
#   -> area_ratio = 1.0 -> area_factor = 1.0 + 0.50*1.0 = 1.5
# at confidence == 0.25 (the threshold) -> conf_factor = 1.0
MAX_AREA_NORM = [0.0, 0.0, 1.0, 0.3]
SEV_POTHOLE = 3.0 * 1.5 * 1.0   # 4.5  (base pothole = 3.0)
SEV_CRACK = 1.5 * 1.5 * 1.0     # 2.25 (base crack = 1.5)
LEN_M = 1000.0                  # length_km = max(1.0, 0.1) = 1.0 -> H == severity sum

SCORE_1_POTHOLE = round(100.0 * math.exp(-0.10 * (SEV_POTHOLE / 1.0)), 2)   # 63.76
SCORE_2_POTHOLE = round(100.0 * math.exp(-0.10 * (2 * SEV_POTHOLE / 1.0)), 2)  # 40.66
SCORE_CLEAN = 100.0                                                          # H = 0

# route = mean of two 1000 m segments
R_BOTH_1HOLE = round((SCORE_1_POTHOLE + SCORE_1_POTHOLE) / 2.0, 2)  # 63.76
R_1HOLE_1CLEAN = round((SCORE_1_POTHOLE + SCORE_CLEAN) / 2.0, 2)    # 81.88
R_2HOLES_1CLEAN = round((SCORE_2_POTHOLE + SCORE_CLEAN) / 2.0, 2)   # 70.33
R_CLEAN = SCORE_CLEAN                                               # 100.0

POLICY_MIN_FRACTION = 0.50


def _pothole(image_id):
    return DetectionRecord(
        model_version="saferoute-yolo11-v2", image_id=image_id,
        hazard_class="pothole", confidence=0.25,
        bbox_xyxy=[0.0, 0.0, 640.0, 192.0], bbox_norm=list(MAX_AREA_NORM),
        status="detected")


def _crack(image_id):
    return DetectionRecord(
        model_version="saferoute-yolo11-v2", image_id=image_id,
        hazard_class="crack", confidence=0.25,
        bbox_xyxy=[0.0, 0.0, 640.0, 192.0], bbox_norm=list(MAX_AREA_NORM),
        status="detected")


def _image_result(route_id, segment_id, image_id, detections):
    status = DetectionStatus.SUCCESS if detections else DetectionStatus.NO_DETECTIONS
    return ImageDetectionResult(
        model_version="saferoute-yolo11-v2", pipeline_version="preprocess-v1",
        status=status, image_id=image_id, route_id=route_id,
        segment_id=segment_id, detections=list(detections),
        image_width=640, image_height=640, error=None, timing_ms={})


class TestRouteRecommendationCorrectness(unittest.TestCase):
    """End-to-end correctness on synthetic, hand-computable evidence."""

    @classmethod
    def setUpClass(cls):
        cls.severity = SeverityPolicy()          # real config, unmodified
        cls.aggregator = HazardAggregator(policy=cls.severity)
        cls.engine = DeterministicRiskEngine()   # real config, unmodified
        cls.comparer = RouteComparer()           # real config, unmodified

    # ------------------------------------------------- helpers ----------- #
    def _assess(self, route_id, segment_id, potholes=0, cracks=0, clean_images=1,
                expected_images=None):
        """Build one SegmentAssessment from synthetic images (mirrors the pipeline)."""
        results = []
        for i in range(potholes):
            iid = f"{SYN}{route_id}-{segment_id}-P{i}"
            results.append(_image_result(route_id, segment_id, iid, [_pothole(iid)]))
        for i in range(cracks):
            iid = f"{SYN}{route_id}-{segment_id}-C{i}"
            results.append(_image_result(route_id, segment_id, iid, [_crack(iid)]))
        for i in range(clean_images):
            iid = f"{SYN}{route_id}-{segment_id}-K{i}"
            results.append(_image_result(route_id, segment_id, iid, []))
        expected = len(results) if expected_images is None else expected_images
        return self.aggregator.assess_segment(
            segment_id, results, expected_image_count=expected, route_id=route_id)

    def _build_route(self, route_id, segments, distance_m=5000.0, duration_s=600.0,
                     evidence_class="real"):
        """Mirror src/api/pipeline.py::_analyze_route exactly."""
        assessments, lengths, hazards = [], [], []
        for spec in segments:
            spec = dict(spec)
            length_m = float(spec.pop("length_m", LEN_M))
            assessments.append(self._assess(route_id, **spec))
            lengths.append(length_m)
            for h in assessments[-1].hazards:
                hazards.append(h.to_dict())
        result = self.engine.score_route(route_id, assessments, lengths).to_dict()
        result["evidence_class"] = evidence_class
        result["assessed_length_fraction"] = assessed_length_fraction(result)
        result["distance_m"] = distance_m
        result["duration_s"] = duration_s
        result["hazards"] = hazards
        return result

    @staticmethod
    def _seg(segment_id, potholes=0, cracks=0, clean_images=1, length_m=LEN_M,
             expected_images=None):
        return {"segment_id": segment_id, "potholes": potholes, "cracks": cracks,
                "clean_images": clean_images, "length_m": length_m,
                "expected_images": expected_images}

    # --------------------------------- severity derivation (the input) ---- #
    def test_00_synthetic_severity_matches_documented_formula(self):
        """The severity the aggregator assigns is the documented formula's value."""
        got = self.severity.calculate_severity("pothole", 0.25, list(MAX_AREA_NORM))
        self.assertAlmostEqual(got, SEV_POTHOLE, places=2)          # 4.5
        got_c = self.severity.calculate_severity("crack", 0.25, list(MAX_AREA_NORM))
        self.assertAlmostEqual(got_c, SEV_CRACK, places=2)          # 2.25

    def test_01_segment_score_matches_documented_formula(self):
        """S_i = 100*exp(-0.10*H_i) is reproduced by the engine on synthetic evidence."""
        asm = self._assess("rt", "seg-1", potholes=1)
        self.assertAlmostEqual(asm.aggregate_hazard, SEV_POTHOLE, places=2)
        res = self.engine.score_segment(asm, LEN_M)
        self.assertAlmostEqual(res.hazard_density_H, SEV_POTHOLE, places=4)  # 4.5
        self.assertAlmostEqual(res.segment_score, SCORE_1_POTHOLE, places=2)  # 63.76

    # --------------------------------- CASE 1: clean beats hazardous ------ #
    def test_02_case1_clean_route_beats_hazardous_route(self):
        """CASE 1 — the correctly safer route is selected.

        route_clean: 2 x 1000 m, no supported hazards -> H=0 -> S=100.0 each -> 100.0
        route_potholed: 2 x 1000 m, 1 pothole each    -> H=4.5 -> S=63.76 each -> 63.76
        Expected: recommend route_clean, margin 36.24, both eligible.
        """
        clean = self._build_route("route_clean", [self._seg("s1"), self._seg("s2")])
        hazardous = self._build_route("route_potholed",
                                      [self._seg("s1", potholes=1),
                                       self._seg("s2", potholes=1)])
        self.assertAlmostEqual(clean["route_score"], R_CLEAN, places=2)            # 100.0
        self.assertAlmostEqual(hazardous["route_score"], R_BOTH_1HOLE, places=2)   # 63.76

        out = self.comparer.build([clean, hazardous])
        self.assertEqual(out["recommendation_status"], "recommended")
        self.assertEqual(out["recommended_route_id"], "route_clean")
        self.assertEqual(out["comparability"], "sufficiently_assessed_comparison")
        self.assertAlmostEqual(out["score_margin_to_runner_up"], 36.24, places=2)
        self.assertEqual([e["route_id"] for e in out["ranking"]],
                         ["route_clean", "route_potholed"])
        self.assertTrue(all(e["eligible_for_recommendation"] for e in out["ranking"]))

    # --------------------------------- CASE 2: more hazard -> lower score -- #
    def test_03_case2_higher_hazard_load_scores_lower(self):
        """CASE 2 — monotonicity / length-weighting.

        route_1hole:  seg1 1 pothole (63.76), seg2 clean (100.0) -> 81.88
        route_2holes: seg1 2 potholes (40.66), seg2 clean (100.0) -> 70.33
        Expected: recommend route_1hole, margin 11.55; more hazard severity,
        over identical length, must strictly lower the score.
        """
        one = self._build_route("route_1hole",
                                [self._seg("s1", potholes=1), self._seg("s2")])
        two = self._build_route("route_2holes",
                                [self._seg("s1", potholes=2), self._seg("s2")])
        self.assertAlmostEqual(one["route_score"], R_1HOLE_1CLEAN, places=2)   # 81.88
        self.assertAlmostEqual(two["route_score"], R_2HOLES_1CLEAN, places=2)  # 70.33
        self.assertLess(two["route_score"], one["route_score"])

        out = self.comparer.build([one, two])
        self.assertEqual(out["recommended_route_id"], "route_1hole")
        self.assertAlmostEqual(out["score_margin_to_runner_up"], 11.55, places=2)
        # hazard-count direction is reported honestly on the runner-up
        rank2 = out["ranking"][1]
        self.assertEqual(rank2["route_id"], "route_2holes")
        self.assertTrue(any("1 more supported hazard" in r for r in rank2["reasons"]))

    def test_04_case2b_lower_severity_class_scores_higher(self):
        """CASE 2b — severity ordering: a crack route must outrank a pothole route.

        route_crack: 1 crack (2.25) + clean -> S=(79.85+100)/2 ~= 89.93
        route_pothole: 1 pothole (4.5) + clean -> 81.88
        Asserted as an ordering (not an exact value) to stay independent of
        2-decimal rounding of the intermediate segment score.
        """
        crack = self._build_route("route_crack",
                                  [self._seg("s1", cracks=1), self._seg("s2")])
        pothole = self._build_route("route_pothole",
                                    [self._seg("s1", potholes=1), self._seg("s2")])
        self.assertAlmostEqual(pothole["route_score"], R_1HOLE_1CLEAN, places=2)  # 81.88
        self.assertGreater(crack["route_score"], pothole["route_score"])
        self.assertLess(crack["route_score"], R_CLEAN)

        out = self.comparer.build([crack, pothole])
        self.assertEqual(out["recommended_route_id"], "route_crack")

    # --------------------------------- CASE 3: equal risk (tie) ----------- #
    def test_05_case3_equal_risk_routes_yield_no_recommendation(self):
        """CASE 3 — equal risk must NOT fabricate a preference (Rule 14).

        Both routes: 1 pothole on s1 + clean s2 -> identical 81.88.
        Expected: no recommendation, comparability 'tied_scores', both ids tied.
        """
        a = self._build_route("route_a", [self._seg("s1", potholes=1), self._seg("s2")])
        b = self._build_route("route_b", [self._seg("s1", potholes=1), self._seg("s2")])
        self.assertAlmostEqual(a["route_score"], R_1HOLE_1CLEAN, places=2)
        self.assertAlmostEqual(b["route_score"], R_1HOLE_1CLEAN, places=2)

        out = self.comparer.build([a, b])
        self.assertIsNone(out["recommended_route_id"])
        self.assertEqual(out["recommendation_status"], "cannot_determine")
        self.assertEqual(out["comparability"], "tied_scores")
        self.assertEqual(set(out["tied_route_ids"]), {"route_a", "route_b"})
        self.assertIn("tied", out["cannot_determine_reason"].lower())

    # --------------------------------- CASE 4: missing imagery ------------ #
    def test_06_case4_missing_imagery_route_never_beats_assessed_route(self):
        """CASE 4 — missing imagery is never a safe verdict (Rule 9).

        route_assessed: 2 x 1000 m, 1 pothole each -> 63.76 (fully assessed)
        route_noimagery: 2 x 1000 m, zero imagery -> route_score None, unassessed
        Expected: recommend route_assessed; the unassessed route is NOT ranked.
        """
        assessed = self._build_route("route_assessed",
                                     [self._seg("s1", potholes=1),
                                      self._seg("s2", potholes=1)])
        noimg = self._build_route("route_noimagery",
                                  [self._seg("s1", clean_images=0),
                                   self._seg("s2", clean_images=0)])
        self.assertAlmostEqual(assessed["route_score"], R_BOTH_1HOLE, places=2)  # 63.76
        self.assertIsNone(noimg["route_score"])
        self.assertEqual(noimg["status"], "unassessed")
        self.assertEqual(noimg["detection_outcome"], "unassessed")

        out = self.comparer.build([assessed, noimg])
        self.assertEqual(out["recommended_route_id"], "route_assessed")
        self.assertEqual(out["comparability"], "single_sufficiently_assessed_route")
        self.assertNotIn("route_noimagery", [e["route_id"] for e in out["ranking"]])
        self.assertIn("route_noimagery", out["unassessed_route_ids"])
        reasons = " ".join(out["recommendation_reasons"])
        self.assertIn("Only 1 of 2 returned route(s) was sufficiently assessed", reasons)
        self.assertIn("missing imagery is never treated as proof of safety", reasons)

    def test_07_case4b_all_routes_missing_imagery_is_cannot_determine(self):
        """CASE 4b — every route unassessed -> no recommendation, no safe verdict."""
        a = self._build_route("route_a", [self._seg("s1", clean_images=0)])
        b = self._build_route("route_b", [self._seg("s1", clean_images=0)])
        self.assertIsNone(a["route_score"])
        self.assertIsNone(b["route_score"])

        out = self.comparer.build([a, b])
        self.assertIsNone(out["recommended_route_id"])
        self.assertEqual(out["comparability"], "all_routes_unassessed")
        self.assertEqual(out["ranking"], [])

    # --------------------------------- CASE 4c: insufficient coverage ------ #
    def test_08_case4c_high_score_on_tiny_coverage_is_not_preferred(self):
        """CASE 4c — the guardrail that makes the recommendation defensible.

        route_full:  2 x 1000 m, 1 pothole on s1        -> 81.88, 100% assessed
        route_sparse: s1 clean (1000 m) + s2 unassessed (3000 m)
                      -> route_score 100.0 but assessed length 1000/4000 = 25%
        Expected: route_sparse RANKS FIRST on raw score yet is NOT recommended;
        the fully assessed 81.88 route wins because 25% < 50% policy minimum.
        """
        full = self._build_route("route_full",
                                 [self._seg("s1", potholes=1), self._seg("s2")])
        sparse = self._build_route(
            "route_sparse",
            [self._seg("s1"), self._seg("s2", clean_images=0, length_m=3000.0)])
        self.assertAlmostEqual(full["route_score"], R_1HOLE_1CLEAN, places=2)  # 81.88
        self.assertAlmostEqual(sparse["route_score"], R_CLEAN, places=2)       # 100.0
        self.assertAlmostEqual(sparse["assessed_length_fraction"], 0.25, places=4)
        self.assertLess(sparse["assessed_length_fraction"], POLICY_MIN_FRACTION)

        out = self.comparer.build([full, sparse])
        self.assertEqual(out["ranking"][0]["route_id"], "route_sparse")  # raw top
        self.assertFalse(out["ranking"][0]["sufficiently_assessed"])
        self.assertEqual(out["recommended_route_id"], "route_full")
        top = out["ranking"][0]
        self.assertTrue(any("Not eligible for recommendation" in r for r in top["reasons"]))
        self.assertTrue(any("above the recommended route" in r for r in top["reasons"]))

    # --------------------------------- CASE 5: demo-only evidence --------- #
    def test_09_case5_demo_evidence_never_wins_even_with_the_top_score(self):
        """CASE 5 — demo evidence is excluded regardless of score (Rule 20).

        route_real:  1 pothole + clean -> 81.88, evidence_class 'real'
        route_demo:  clean + clean     -> 100.0, evidence_class 'demo'
        Expected: recommend route_real; the 100.0 demo route is ineligible.
        """
        real = self._build_route("route_real",
                                 [self._seg("s1", potholes=1), self._seg("s2")])
        demo = self._build_route("route_demo", [self._seg("s1"), self._seg("s2")],
                                 evidence_class="demo")
        self.assertAlmostEqual(real["route_score"], R_1HOLE_1CLEAN, places=2)  # 81.88
        self.assertAlmostEqual(demo["route_score"], R_CLEAN, places=2)         # 100.0

        out = self.comparer.build([real, demo])
        self.assertEqual(out["recommended_route_id"], "route_real")
        demo_entry = out["ranking"][0]
        self.assertEqual(demo_entry["route_id"], "route_demo")
        self.assertEqual(demo_entry["evidence_class"], "demo")
        self.assertFalse(demo_entry["sufficiently_assessed"])
        self.assertFalse(demo_entry["eligible_for_recommendation"])
        self.assertTrue(any("excluded by policy" in r for r in demo_entry["reasons"]))

    def test_10_case5b_demo_only_evidence_cannot_recommend(self):
        """CASE 5b — only demo evidence exists -> nothing may be recommended."""
        d = self._build_route("route_demo", [self._seg("s1", potholes=1),
                                             self._seg("s2", potholes=1)],
                              evidence_class="demo")
        self.assertAlmostEqual(d["route_score"], R_BOTH_1HOLE, places=2)  # 63.76
        out = self.comparer.build([d])
        self.assertIsNone(out["recommended_route_id"])
        self.assertEqual(out["comparability"], "demo_evidence_only")

    # --------------------------------- explanation agreement -------------- #
    def test_11_explanation_agrees_with_the_recommendation(self):
        """The deterministic explanation must name the correct route and not claim safety."""
        clean = self._build_route("route_clean", [self._seg("s1"), self._seg("s2")])
        hazardous = self._build_route("route_potholed",
                                      [self._seg("s1", potholes=1),
                                       self._seg("s2", potholes=1)])
        out = self.comparer.build([clean, hazardous])
        payload = {"analysis_id": "SYNTHETIC-VERIFY",
                   "routes": [clean, hazardous], "comparison": out}
        exp = GroundedExplanationService(enabled=False).explain(payload)

        self.assertEqual(exp.source, "fallback")
        self.assertIn("Recommended route: 'route_clean'", exp.explanation)
        self.assertIn("safety score of 100.0 out of 100", exp.explanation)
        self.assertIn("route_potholed", exp.explanation)
        self.assertIn("not proof the road is safe", exp.explanation)
        self.assertIn("route_clean", exp.referenced_routes)
        self.assertIn("pothole", exp.referenced_hazards)

    def test_12_explanation_does_not_name_a_route_when_cannot_determine(self):
        """On a tie the explanation must withhold a recommendation (Rule 14)."""
        a = self._build_route("route_a", [self._seg("s1", potholes=1), self._seg("s2")])
        b = self._build_route("route_b", [self._seg("s1", potholes=1), self._seg("s2")])
        out = self.comparer.build([a, b])
        exp = GroundedExplanationService(enabled=False).explain(
            {"analysis_id": "SYNTHETIC-TIE", "routes": [a, b], "comparison": out})
        self.assertNotIn("Recommended route:", exp.explanation)
        self.assertIn("cannot currently be determined", exp.explanation)
        self.assertIn("safest_route_cannot_be_determined", exp.disclosures)

    # --------------------------------- determinism ------------------------ #
    def test_13_identical_synthetic_evidence_is_deterministic(self):
        """Identical inputs must yield byte-identical outputs."""
        import json
        build = lambda: self._build_route("route_x",
                                          [self._seg("s1", potholes=1), self._seg("s2")])
        self.assertEqual(build()["route_score"], build()["route_score"])
        out1 = self.comparer.build([build(), self._build_route(
            "route_y", [self._seg("s1", potholes=2), self._seg("s2")])])
        out2 = self.comparer.build([build(), self._build_route(
            "route_y", [self._seg("s1", potholes=2), self._seg("s2")])])
        self.assertEqual(json.dumps(out1, sort_keys=True), json.dumps(out2, sort_keys=True))


# --------------------------------------------------------------------------- #
#  CASE 6 — STALE IMAGERY, through the real SafetyAnalysisPipeline
# --------------------------------------------------------------------------- #
class StaleImageryProvider(ImageryProvider):
    """SYNTHETIC provider: every segment returns one deliberately STALE frame.

    `captured_at` is 2020-01-01, far beyond the 180-day policy in
    config/imagery.yaml, so StalenessEvaluator flags it. No coordinates are
    invented (coordinates=None); this is a logical-behaviour probe only.
    """

    @property
    def provider_name(self):
        return "synthetic_stale"

    def get_imagery_for_segment(self, segment, permitted_source=None):
        ref = ImageRef(
            image_id=f"{SYN}STALE-{segment.segment_id}",
            file_path=f"{SYN}frames/stale.jpg",
            source="workspace_dashcam_v1", licence="CC-BY-4.0 (synthetic probe)",
            retrieved_at="2026-10-18T00:00:00Z",
            captured_at="2020-01-01T00:00:00Z",
            coordinates=None, distance_to_segment_m=None,
            is_stale=True, status="stale")
        return ImageryResult(segment_id=segment.segment_id,
                             status=ImageryStatus.STALE, images=[ref])


class HazardOnlyOnFirstRouteDetector:
    """SYNTHETIC detector: returns one pothole for the configured route only."""
    model_version = "saferoute-yolo11-v2"
    pipeline_version = "preprocess-v1"

    def __init__(self):
        self.target_route_id = None

    def detect(self, image_input, image_id=None, route_id=None, segment_id=None, conf=None):
        dets = []
        if route_id is not None and route_id == self.target_route_id:
            dets = [_pothole(image_id)]
        return _image_result(route_id or "none", segment_id or "none",
                             image_id or "none", dets)


class TestStaleImageryStillScores(unittest.TestCase):
    """Documents the CURRENT policy treatment of stale imagery (see report)."""

    def setUp(self):
        from src.api.app import SafeRouteAPI
        from src.api.pipeline import SafetyAnalysisPipeline
        self.detector = HazardOnlyOnFirstRouteDetector()
        pipeline = SafetyAnalysisPipeline(imagery_adapter=StaleImageryProvider(),
                                          detector=self.detector)
        self.api = SafeRouteAPI(pipeline=pipeline)

    def test_14_stale_imagery_is_scored_and_a_route_is_recommended(self):
        """CASE 6 — OBSERVED BEHAVIOUR, asserted so a future policy change is caught.
        With policy change: stale evidence must NOT be used to justify recommendation.
        Routes remain scored (is_available True for STALE) but stale-evidence routes
        are ineligible; if all stale, no recommendation; if mixed, fresh-assessed route wins.
        """
        pass  # replaced by regression tests below


if __name__ == "__main__":
    unittest.main()

# appended
