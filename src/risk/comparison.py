"""SafeRoute AI — Deterministic Route Comparison & Recommendation Policy.

Compares the route scores ALREADY computed by the deterministic risk engine and
decides whether the available evidence supports a defensible safest-route
recommendation (master_rules.md Rules 7, 9, 10, 12, 14, 20).

Hard invariants:
- This module never computes, alters or invents a safety score (Rule 7). It is a
  pure function over verified route-score records produced upstream.
- Unassessed routes are never ranked or presented as safe (Rule 9).
- Routes scored from demo imagery (not geographically matched to the requested
  roads) are excluded from the real-world recommendation (Rule 9, Rule 20).
- A route is only recommendable when a documented minimum fraction of its
  length actually carries a score ("sufficiently assessed").
- Tied top scores mean the evidence does NOT support declaring one route
  safer; no recommendation is issued (Rule 14: never fabricate a preference).
- Identical inputs always produce an identical output (determinism).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml

DEFAULT_POLICY_CONFIG = Path("config/route_comparison.yaml")
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

HONESTY_NOTE = (
    "Unassessed routes are never ranked or presented as safe (Rule 9). "
    "A score of 100 means no supported hazard was detected in the available "
    "imagery — it is NOT proof the road is safe."
)


def load_comparison_policy(
    config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Load the route-comparison policy (workspace-local, fail-loud on absence)."""
    p = Path(config_path) if config_path else (WORKSPACE_ROOT / DEFAULT_POLICY_CONFIG)
    if not p.is_file():
        raise FileNotFoundError(f"Route comparison policy not found at {p}")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def assessed_length_fraction(route: Dict[str, Any]) -> float:
    """Fraction of a route's total segment length that carries a score.

    Derived purely arithmetically from the engine's own segment results — no
    score is computed or modified here (Rule 7). Segments without a score
    (unassessed / failed / suppressed) contribute zero assessed length.
    """
    segs = route.get("segment_scores") or []
    total = 0.0
    scored = 0.0
    for s in segs:
        length = float(s.get("length_m") or 0.0)
        total += length
        if s.get("segment_score") is not None:
            scored += length
    if total <= 0.0:
        return 0.0
    return round(scored / total, 4)


def hazard_segments(route: Dict[str, Any]) -> List[str]:
    """Ordered unique segment IDs carrying at least one supported hazard."""
    seen: List[str] = []
    for h in route.get("hazards") or []:
        seg = h.get("segment_id")
        if seg and seg not in seen:
            seen.append(seg)
    return seen


def _magnitude_phrase(value: float, unit: str) -> str:
    return f"{abs(value):.0f} {unit} {'more' if value > 0 else 'less'}"


class RouteComparer:
    """Pure, deterministic comparison of verified route-score records."""

    def __init__(self, policy: Optional[Dict[str, Any]] = None):
        self.policy = policy if policy is not None else load_comparison_policy()
        rec = (self.policy.get("recommendation") or {})
        guard = (self.policy.get("guardrails") or {})
        self.min_assessed_length_fraction = float(rec.get("min_assessed_length_fraction", 0.50))
        self.tie_tolerance_score = float(rec.get("tie_tolerance_score", 0.0))
        self.never_recommend_demo = bool(guard.get("never_recommend_demo_evidence", True))

    # ------------------------------------------------------------------ #
    def build(self, routes: List[Dict[str, Any]], assessed_at: Optional[str] = None) -> Dict[str, Any]:
        """Build the comparison/recommendation block from verified route records."""
        scored = [r for r in routes if r.get("route_score") is not None]
        unassessed = [r for r in routes if r.get("route_score") is None]

        enriched: List[Dict[str, Any]] = []
        for r in scored:
            frac = assessed_length_fraction(r)
            is_demo = bool(r.get("evidence_class") == "demo")
            eligible = frac >= self.min_assessed_length_fraction
            if self.never_recommend_demo and is_demo:
                eligible = False
            enriched.append({
                "route": r,
                "assessed_length_fraction": frac,
                "is_demo": is_demo,
                "eligible": eligible,
            })

        ranked = sorted(enriched, key=lambda e: e["route"]["route_score"], reverse=True)
        candidates = [e for e in ranked if e["eligible"]]
        state = self._decide(ranked, candidates, had_routes=bool(routes))

        return {
            "ranking": [
                self._rank_entry(i + 1, e, state) for i, e in enumerate(ranked)
            ],
            "recommended_route_id": state["recommended_route_id"],
            "recommendation_reasons": state["reasons"],
            "recommendation_status": state["status"],
            "comparability": state["comparability"],
            "cannot_determine_reason": state["cannot_determine_reason"],
            "tied_route_ids": state["tied_route_ids"],
            "score_margin_to_runner_up": state["margin"],
            "min_assessed_length_fraction": self.min_assessed_length_fraction,
            "unassessed_route_ids": [r["route_id"] for r in unassessed],
            "assessed_at": assessed_at,
            "note": HONESTY_NOTE,
        }

    # ------------------------------------------------------------------ #
    def _decide(
        self,
        ranked: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        had_routes: bool = False,
    ) -> Dict[str, Any]:
        state: Dict[str, Any] = {
            "status": "cannot_determine",
            "recommended_route_id": None,
            "comparability": "no_sufficiently_assessed_route",
            "cannot_determine_reason": None,
            "tied_route_ids": [],
            "margin": None,
            "reasons": [],
            "top": None,
        }

        if not ranked:
            if had_routes:
                state["comparability"] = "all_routes_unassessed"
                state["cannot_determine_reason"] = (
                    "all_routes_unassessed: none of the returned routes produced a score "
                    "because road imagery was missing or insufficient; the safest route "
                    "cannot be determined."
                )
            else:
                state["comparability"] = "no_routes_scored"
                state["cannot_determine_reason"] = (
                    "no_routes_scored: no returned route produced a deterministic score, "
                    "so no comparison is possible."
                )
            return state

        if not candidates:
            if all(e["is_demo"] for e in ranked):
                state["comparability"] = "demo_evidence_only"
                state["cannot_determine_reason"] = (
                    "demo_evidence_only: the only scores came from demo imagery, which is "
                    "not geographically matched to the requested roads and is never used "
                    "for a real-world recommendation."
                )
            else:
                state["comparability"] = "no_sufficiently_assessed_route"
                best_frac = max(e["assessed_length_fraction"] for e in ranked)
                state["cannot_determine_reason"] = (
                    f"no_sufficiently_assessed_route: no route reached the minimum assessed "
                    f"length of {self.min_assessed_length_fraction:.0%} "
                    f"(best was {best_frac:.0%}); the safest route cannot be determined."
                )
            return state

        top = candidates[0]
        top_score = top["route"]["route_score"]

        if len(candidates) > 1:
            runner = candidates[1]
            margin = round(top_score - runner["route"]["route_score"], 4)
            if abs(margin) <= self.tie_tolerance_score:
                state["tied_route_ids"] = [e["route"]["route_id"] for e in candidates]
                state["comparability"] = "tied_scores"
                state["cannot_determine_reason"] = (
                    "tied_scores: the top sufficiently assessed routes have equal safety "
                    "scores, so the evidence does not support declaring one safer."
                )
                state["margin"] = margin
                return state
            state["margin"] = margin

        state["status"] = "recommended"
        state["recommended_route_id"] = top["route"]["route_id"]
        state["top"] = top
        state["comparability"] = (
            "single_sufficiently_assessed_route" if len(candidates) == 1
            else "sufficiently_assessed_comparison"
        )
        state["reasons"] = self._recommendation_reasons(top, candidates, ranked)
        return state

    # ------------------------------------------------------------------ #
    def _recommendation_reasons(
        self,
        top: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        ranked: List[Dict[str, Any]],
    ) -> List[str]:
        route = top["route"]
        seg_count = len(hazard_segments(route))
        reasons: List[str] = [
            f"Highest deterministic safety score ({route['route_score']}/100) among "
            f"{len(candidates)} sufficiently assessed route(s); "
            f"{route.get('hazards_total', 0)} supported hazard detection(s) on "
            f"{seg_count} assessed segment(s)."
        ]

        for other in candidates[1:]:
            o = other["route"]
            delta = round(route["route_score"] - o["route_score"], 2)
            hazard_delta = int(route.get("hazards_total", 0)) - int(o.get("hazards_total", 0))
            parts = [f"Versus '{o['route_id']}': score {delta:+.2f} points"]
            if hazard_delta != 0:
                parts.append(
                    f"{abs(hazard_delta)} {'fewer' if hazard_delta > 0 else 'more'} "
                    f"supported hazard detection(s)"
                )
            d_dist = round(float(route.get("distance_m") or 0.0) - float(o.get("distance_m") or 0.0))
            d_time = round(float(route.get("duration_s") or 0.0) - float(o.get("duration_s") or 0.0))
            if d_dist:
                parts.append(f"{abs(d_dist)} m {'shorter' if d_dist < 0 else 'longer'}")
            if d_time:
                parts.append(f"{abs(d_time):.0f} s {'faster' if d_time < 0 else 'slower'}")
            reasons.append(", ".join(parts) + ".")

        if len(candidates) == 1 and len(ranked) > 1:
            reasons.append(
                f"Only 1 of {len(ranked)} scored route(s) had sufficient assessed coverage; "
                f"the other scored route(s) could not be defensibly compared."
            )
        elif len(candidates) < len(ranked):
            reasons.append(
                f"{len(ranked) - len(candidates)} scored route(s) were excluded from the "
                f"recommendation (insufficient assessed length or demo evidence)."
            )
        if any(e["is_demo"] for e in ranked):
            reasons.append(
                "Route(s) scored from demo imagery were excluded: demo imagery is not "
                "geographically matched to the requested roads."
            )
        reasons.append(
            "Unassessed route(s) were not compared: missing imagery is never treated "
            "as proof of safety."
        )
        return reasons

    # ------------------------------------------------------------------ #
    def _rank_entry(
        self,
        rank: int,
        entry: Dict[str, Any],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        route = entry["route"]
        out: Dict[str, Any] = {
            "rank": rank,
            "route_id": route["route_id"],
            "route_score": route["route_score"],
            "status": route.get("status"),
            "coverage": route.get("coverage"),
            "assessed_length_fraction": entry["assessed_length_fraction"],
            "sufficiently_assessed": (
                entry["assessed_length_fraction"] >= self.min_assessed_length_fraction
            ),
            "eligible_for_recommendation": entry["eligible"],
            "evidence_class": "demo" if entry["is_demo"] else "real",
            "distance_m": route.get("distance_m"),
            "duration_s": route.get("duration_s"),
            "hazards_total": route.get("hazards_total", 0),
            "hazard_segments": hazard_segments(route),
            "detection_outcome": route.get("detection_outcome", "unassessed"),
            "safety_note": route.get("safety_note", ""),
            "reasons": self._route_reasons(rank, entry, state),
        }

        top = state.get("top")
        if top is not None:
            tr = top["route"]
            out["score_delta_vs_recommended"] = round(
                route["route_score"] - tr["route_score"], 2)
            out["distance_delta_vs_recommended"] = round(
                float(route.get("distance_m") or 0.0) - float(tr.get("distance_m") or 0.0), 1)
            out["duration_delta_vs_recommended"] = round(
                float(route.get("duration_s") or 0.0) - float(tr.get("duration_s") or 0.0), 1)
        else:
            out["score_delta_vs_recommended"] = None
            out["distance_delta_vs_recommended"] = None
            out["duration_delta_vs_recommended"] = None
        return out

    def _route_reasons(self, rank: int, entry: Dict[str, Any], state: Dict[str, Any]) -> List[str]:
        route = entry["route"]
        top = state.get("top")
        reasons: List[str] = []

        if entry["is_demo"]:
            reasons.append(
                "Scored from demo imagery that is not geographically matched to this "
                "route; pipeline-demonstration evidence only, never a real-world "
                "safety claim (Rule 9, Rule 20)."
            )

        if top is not None and route["route_id"] == top["route"]["route_id"]:
            reasons.append(
                "Ranked first: highest deterministic score among sufficiently assessed routes."
            )
        elif top is not None:
            delta = round(route["route_score"] - top["route"]["route_score"], 2)
            if delta < 0:
                reasons.append(
                    f"Ranks below '{top['route']['route_id']}' by {abs(delta):.2f} deterministic "
                    f"score points on the assessed evidence."
                )
            elif delta > 0:
                reasons.append(
                    f"Raw score is {delta:.2f} points above the recommended route "
                    f"'{top['route']['route_id']}', but this route is not eligible for "
                    f"recommendation on the assessed evidence."
                )
            else:
                reasons.append(
                    f"Tied on deterministic score with the recommended route "
                    f"'{top['route']['route_id']}'."
                )
        elif state["tied_route_ids"]:
            reasons.append(
                "Tied with the other top route(s) on identical deterministic scores; "
                "the evidence does not support declaring one safer."
            )

        if not entry["eligible"]:
            reasons.append(
                f"Not eligible for recommendation: only {entry['assessed_length_fraction']:.0%} "
                f"of the route length was assessed (policy minimum "
                f"{self.min_assessed_length_fraction:.0%})."
            )
        elif top is not None and route["route_id"] != top["route"]["route_id"]:
            hazard_delta = int(route.get("hazards_total", 0)) - int(top["route"].get("hazards_total", 0))
            if hazard_delta > 0:
                segs = ", ".join(hazard_segments(route)[:4])
                reasons.append(
                    f"Supports {hazard_delta} more supported hazard detection(s) than the "
                    f"recommended route"
                    + (f" (on segment(s) {segs})." if segs else ".")
                )
            elif hazard_delta == 0 and route.get("detection_outcome") == "insufficient_coverage":
                reasons.append(
                    "Only part of this route had assessable imagery; the unassessed "
                    "remainder must not be treated as safe."
                )
            d_dist = round(float(route.get("distance_m") or 0.0) - float(top["route"].get("distance_m") or 0.0))
            d_time = round(float(route.get("duration_s") or 0.0) - float(top["route"].get("duration_s") or 0.0))
            trade: List[str] = []
            if d_dist:
                trade.append(_magnitude_phrase(d_dist, "m") + " in distance")
            if d_time:
                trade.append(_magnitude_phrase(d_time, "s") + " in travel time")
            if trade:
                reasons.append("Versus the recommended route: " + ", ".join(trade) + ".")
        return reasons
