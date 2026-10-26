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

TRAVEL_TIME_NOTE = (
    "Travel time is the routing provider's own estimate for that route. When the "
    "routes came from different routing providers, the durations come from "
    "different speed models and are not directly comparable; no travel-time "
    "difference is claimed between them."
)


def route_provider(route: Dict[str, Any]) -> Optional[str]:
    """The routing provider that returned ``route`` (None when unknown)."""
    provider = route.get("provider")
    if isinstance(provider, str) and provider.strip():
        return provider.strip()
    return None


def providers_differ(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Whether two routes are KNOWN to come from different routing providers.

    Durations are only comparable within one provider's speed model: a
    cross-provider duration difference measures the two engines' assumptions,
    not a real difference between the roads, so it is never stated as one.

    Only an explicit difference counts. When the provider is unknown, no
    cross-provider statement is made in either direction: the durations are
    compared (nothing is known to contradict it) but no "different engines"
    claim is made either.
    """
    provider_a = route_provider(a)
    provider_b = route_provider(b)
    if provider_a is None or provider_b is None:
        return False
    return provider_a != provider_b


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
        if s.get("is_suppressed"):
            continue
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
    def _is_sufficiently_assessed(self, fraction: float, is_demo: bool, is_stale: bool = False) -> bool:
        """Policy test for whether a scored route may take part in a recommendation.

        A route is sufficiently assessed only when it carries the documented
        minimum assessed length AND its evidence class is admitted by policy.
        When `never_recommend_demo_evidence` is active, demo evidence does not
        qualify as sufficiently assessed (Rule 9, Rule 20).
        Stale evidence must not qualify a route for recommendation (Rule 9).
        """
        if fraction < self.min_assessed_length_fraction:
            return False
        if self.never_recommend_demo and is_demo:
            return False
        if is_stale:
            return False
        return True

    # ------------------------------------------------------------------ #
    def build(self, routes: List[Dict[str, Any]], assessed_at: Optional[str] = None) -> Dict[str, Any]:
        """Build the comparison/recommendation block from verified route records."""
        scored = [r for r in routes if r.get("route_score") is not None]
        unassessed = [r for r in routes if r.get("route_score") is None]

        enriched: List[Dict[str, Any]] = []
        for r in scored:
            frac = assessed_length_fraction(r)
            is_demo = bool(r.get("evidence_class") == "demo")
            is_stale_evidence = bool(r.get("evidence_class") == "stale")
            eligible = self._is_sufficiently_assessed(frac, is_demo, is_stale_evidence)
            enriched.append({
                "route": r,
                "assessed_length_fraction": frac,
                "is_demo": is_demo,
                "is_stale_evidence": is_stale_evidence,
                "eligible": eligible,
            })

        ranked = sorted(enriched, key=lambda e: e["route"]["route_score"], reverse=True)
        candidates = [e for e in ranked if e["eligible"]]
        state = self._decide(
            ranked,
            candidates,
            had_routes=bool(routes),
            unassessed_count=len(unassessed),
        )

        providers: List[str] = []
        for route in routes:
            provider = route_provider(route)
            if provider and provider not in providers:
                providers.append(provider)

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
            # PHASE_30: which routing providers actually contributed a route,
            # and the standing note that makes cross-provider travel times
            # honest instead of silently misleading.
            "providers": providers,
            "travel_time_note": TRAVEL_TIME_NOTE,
        }

    # ------------------------------------------------------------------ #
    def _decide(
        self,
        ranked: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        had_routes: bool = False,
        unassessed_count: int = 0,
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
                stale_only = all(e.get("is_stale_evidence") for e in ranked)
                state["comparability"] = "no_sufficiently_assessed_route"
                best_frac = max(e["assessed_length_fraction"] for e in ranked)
                if stale_only:
                    state["cannot_determine_reason"] = (
                        "no_sufficiently_assessed_route: every scored route relied on "
                        "stale imagery (capture beyond policy age or unverifiable), and "
                        "stale evidence is never used to justify a recommendation; the "
                        "safest route cannot be determined."
                    )
                else:
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
        state["reasons"] = self._recommendation_reasons(
            top, candidates, ranked, unassessed_count)
        return state

    # ------------------------------------------------------------------ #
    def _recommendation_reasons(
        self,
        top: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        ranked: List[Dict[str, Any]],
        unassessed_count: int = 0,
    ) -> List[str]:
        route = top["route"]
        seg_count = len(hazard_segments(route))
        cross_provider = False
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
            if d_dist:
                parts.append(f"{abs(d_dist)} m {'shorter' if d_dist < 0 else 'longer'}")
            # Travel times are each routing provider's own estimate. A delta is
            # only meaningful when both routes came from the SAME engine; a
            # cross-provider delta compares two speed models, not two roads,
            # so it is never stated as a difference between the routes.
            if not providers_differ(route, o):
                d_time = round(
                    float(route.get("duration_s") or 0.0) - float(o.get("duration_s") or 0.0)
                )
                if d_time:
                    parts.append(f"{abs(d_time):.0f} s {'faster' if d_time < 0 else 'slower'}")
            else:
                cross_provider = True
            reasons.append(", ".join(parts) + ".")

        if cross_provider:
            reasons.append(
                "Travel times above are each routing provider's own estimate: the routes "
                "were returned by different routing engines with different speed models, so "
                "their durations are not directly comparable and no travel-time difference "
                "is claimed between them."
            )

        total_routes = len(ranked) + unassessed_count
        if len(candidates) == 1 and total_routes > 1:
            others = total_routes - 1
            reasons.append(
                f"Only 1 of {total_routes} returned route(s) was sufficiently assessed; "
                f"the other {others} route(s) could not be defensibly compared."
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
        if any(e.get("is_stale_evidence") for e in ranked):
            reasons.append(
                "Stale imagery was not used to justify a recommendation; freshness could "
                "not be verified as current."
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
            "sufficiently_assessed": self._is_sufficiently_assessed(
                entry["assessed_length_fraction"], entry["is_demo"], entry.get("is_stale_evidence", False)),
            "eligible_for_recommendation": entry["eligible"],
            "evidence_class": (
                "demo" if entry["is_demo"]
                else ("stale" if entry.get("is_stale_evidence") else "real")
            ),
            "distance_m": route.get("distance_m"),
            "duration_s": route.get("duration_s"),
            # PHASE_30: the routing provider that actually returned this route.
            # The UI attributes the route (and its own travel-time estimate)
            # to it instead of pretending every route came from one engine.
            "provider": route_provider(route),
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

        if entry.get("is_stale_evidence"):
            reasons.append(
                "Stale imagery: freshness could not be verified as current; evidence is not "
                "used to support a recommendation."
            )
        if not entry["eligible"]:
            if entry["is_demo"] and self.never_recommend_demo:
                reasons.append(
                    "Not eligible for recommendation: evidence class 'demo' is excluded "
                    "by policy from real-world recommendations."
                )
            elif entry.get("is_stale_evidence"):
                reasons.append(
                    "Not eligible for recommendation: imagery freshness is stale or unverifiable; "
                    "stale evidence is not used to justify a recommendation."
                )
            else:
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
            trade: List[str] = []
            if d_dist:
                trade.append(_magnitude_phrase(d_dist, "m") + " in distance")
            # Only compare travel times within the SAME routing provider — see
            # `same_provider` for why a cross-provider delta is not a real
            # difference between the two roads.
            if not providers_differ(route, top["route"]):
                d_time = round(
                    float(route.get("duration_s") or 0.0) - float(top["route"].get("duration_s") or 0.0)
                )
                if d_time:
                    trade.append(_magnitude_phrase(d_time, "s") + " in travel time")
            elif providers_differ(route, top["route"]):
                reasons.append(
                    "Travel time is this route's own routing-provider estimate; the "
                    "recommended route came from a different routing engine, so the two "
                    "durations are not directly comparable and no travel-time difference "
                    "is claimed."
                )
            if trade:
                reasons.append("Versus the recommended route: " + ", ".join(trade) + ".")
        return reasons
