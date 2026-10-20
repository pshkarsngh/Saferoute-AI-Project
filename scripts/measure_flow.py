"""Live latency probe for the two-phase SafeRoute UI flow (PHASE_27).

Measures, against a running server:
  * POST /api/routes  — fast routing-provider geometry preview
  * POST /api/analyze — full assessment, plus its own timings_ms breakdown

Usage: python scripts/measure_flow.py <port> <routes_body.json> <analyze_body.json>
"""

import json
import sys
import time
import urllib.request


def post(port: int, path: str, body: dict) -> tuple[float, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as resp:
        payload = json.loads(resp.read().decode())
    return time.perf_counter() - t0, payload


def main() -> None:
    port = int(sys.argv[1])
    with open(sys.argv[2], encoding="utf-8") as fh:
        routes_body = json.load(fh)
    with open(sys.argv[3], encoding="utf-8") as fh:
        analyze_body = json.load(fh)

    routes_s, routes_resp = post(port, "/api/routes", routes_body)
    print(f"routes_ms={routes_s * 1000:.0f} routes={len(routes_resp.get('routes', []))}")

    analyze_s, rec = post(port, "/api/analyze", analyze_body)
    print(f"analyze_ms={analyze_s * 1000:.0f} routes={len(rec.get('routes', []))}")
    print("backend_timings_ms=" + json.dumps(rec.get("timings_ms", {}), sort_keys=True))
    print(f"status={rec.get('status')} recommendation={rec.get('recommendation')}")
    print(
        "evidence="
        + ",".join(str(r.get("evidence_class")) for r in rec.get("routes", []))
    )
    print(
        "scores="
        + ",".join(str(r.get("route_score")) for r in rec.get("routes", []))
    )
    print("limitations=" + json.dumps(rec.get("limitations", [])))
    if len(sys.argv) > 4:
        with open(sys.argv[4], "w", encoding="utf-8") as fh:
            json.dump(rec, fh)


if __name__ == "__main__":
    main()
