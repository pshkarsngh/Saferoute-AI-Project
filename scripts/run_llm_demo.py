#!/usr/bin/env python3
r"""SafeRoute AI — run the grounded LLM (Ollama) directly.

Sends a small, fully verified payload through the SAME explainer the API uses
(``GroundedExplanationService``) and prints the result, so you can confirm the
local model is answering (:``source: "ollama"``) instead of falling back.

Usage:
    .\.venv\Scripts\python.exe scripts\run_llm_demo.py
    .\.venv\Scripts\python.exe scripts\run_llm_demo.py --question "avoid potholes"
    .\.venv\Scripts\python.exe scripts\run_llm_demo.py --raw   # plain Ollama call

Requires Ollama serving at the configured base_url (127.0.0.1:11434) with the
configured model pulled (``ollama list``). No data is invented: the sample
payload below is the only evidence the model is allowed to explain.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.api.bootstrap import build_explainer  # noqa: E402
from src.config import load_settings  # noqa: E402

SAMPLE_PAYLOAD = {
    "analysis_id": "demo-analysis",
    "model_version": "yolo-baseline",
    "config_hash": "demo",
    "status": "ok",
    "routes": [
        {
            "route_id": "route_a",
            "route_score": 84.2,
            "status": "assessed",
            "coverage": {"images_used": 18, "images_total": 20, "fraction": 0.9},
            "assessed_length_fraction": 0.9,
            "distance_m": 4200,
            "duration_s": 720,
            "evidence_class": "real",
            "hazards": [
                {"hazard_class": "pothole", "severity": "moderate", "segment_id": "seg-a-03"},
                {"hazard_class": "pothole", "severity": "low", "segment_id": "seg-a-07"},
            ],
        },
        {
            "route_id": "route_b",
            "route_score": 61.5,
            "status": "assessed",
            "coverage": {"images_used": 15, "images_total": 20, "fraction": 0.75},
            "assessed_length_fraction": 0.75,
            "distance_m": 5300,
            "duration_s": 960,
            "evidence_class": "real",
            "hazards": [
                {"hazard_class": "waterlogging", "severity": "high", "segment_id": "seg-b-02"},
            ],
        },
    ],
    "comparison": {
        "recommended_route_id": "route_a",
        "recommendation_status": "recommended",
        "comparability": "comparable",
        "ranking": [
            {"rank": 1, "route_id": "route_a", "route_score": 84.2},
            {"rank": 2, "route_id": "route_b", "route_score": 61.5},
        ],
        "recommendation_reasons": ["route_a has the higher assessed safety score"],
    },
    "limitations": ["imagery covers part of each route"],
}


def raw_ollama_call(base_url: str, model: str, timeout: float, prompt: str) -> str:
    """Minimal direct call to Ollama's /api/generate (no grounding layer)."""
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8")).get("response", "")


def main() -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Run the SafeRoute AI grounded LLM.")
    parser.add_argument("--question", default=None, help="optional user preference text")
    parser.add_argument("--raw", action="store_true", help="bypass grounding, call Ollama directly")
    args = parser.parse_args()

    print(f"Ollama: {settings.llm_base_url}  model: {settings.llm_model}  "
          f"enabled: {settings.llm_enabled}  timeout: {settings.llm_timeout_seconds}s")

    if args.raw:
        reply = raw_ollama_call(
            settings.llm_base_url, settings.llm_model, settings.llm_timeout_seconds,
            args.question or "Say hello in one short sentence.",
        )
        print(reply.strip())
        return 0

    explainer = build_explainer(settings)
    if not explainer.enabled:
        print("LLM is disabled in config/.env — set llm.enabled or OLLAMA_BASE_URL.")
        return 1

    result = explainer.explain(SAMPLE_PAYLOAD, user_preferences=args.question)
    print(json.dumps(result.to_dict(), indent=2))

    if result.source != "ollama":
        print(f"\nFell back to deterministic text. Reason: {explainer.last_error}",
              file=sys.stderr)
        return 2
    print("\nLive grounded reply from Ollama.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
