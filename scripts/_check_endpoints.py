"""End-to-end API endpoint check against the running server.

Hits every documented endpoint, plus error/validation paths, and prints a
pass/fail table. Never prints secrets.
"""
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
RESULTS = []


def call(name, method, path, data=None, timeout=180, expect=None):
    url = BASE + path
    hdrs = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data is not None else None
    started = time.time()
    try:
        r = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            code = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        code = e.code
    except Exception as e:  # noqa: BLE001
        RESULTS.append({"name": name, "pass": False, "ms": round((time.time() - started) * 1000),
                        "detail": f"{type(e).__name__}: {e}"})
        return None
    ms = round((time.time() - started) * 1000)
    try:
        payload = json.loads(raw)
    except Exception:  # noqa: BLE001
        payload = {"_raw": raw[:200].decode("utf-8", "replace")}
    ok = (code == expect) if expect is not None else (200 <= code < 300)
    RESULTS.append({"name": name, "pass": ok, "http": code, "ms": ms,
                    "detail": _summ(payload) if not ok else ""})
    return payload


def _summ(p):
    if isinstance(p, dict):
        for k in ("error", "message", "code", "detail"):
            if k in p:
                v = p[k]
                return f"{k}={v if not isinstance(v, dict) else json.dumps(v)[:160]}"
        return json.dumps(p)[:200]
    return str(p)[:200]


# ---------- GET endpoints ----------
call("GET /api/health", "GET", "/api/health")
call("GET /api/config", "GET", "/api/config")
call("GET / (UI index)", "GET", "/")
call("GET /runtime-config.js", "GET", "/runtime-config.js")

# ---------- Geocoding ----------
geo = call("POST /api/geocode (valid)", "POST", "/api/geocode", {"query": "Bengaluru", "limit": 1})
call("POST /api/geocode (missing query)", "POST", "/api/geocode", {}, expect=400)

# ---------- Routing ----------
routes = call("POST /api/routes (coords)", "POST", "/api/routes", {
    "origin": {"latitude": 12.9716, "longitude": 77.5946},
    "destination": {"latitude": 12.9784, "longitude": 77.6408},
})
call("POST /api/routes (invalid coord)", "POST", "/api/routes", {
    "origin": {"latitude": 999, "longitude": 77.59},
    "destination": {"latitude": 12.9784, "longitude": 77.6408},
}, expect=400)
call("POST /api/routes (missing location)", "POST", "/api/routes", {}, expect=400)
call("POST /api/routes (place names)", "POST", "/api/routes", {
    "origin_query": "MG Road Bengaluru", "destination_query": "Whitefield Bengaluru",
    "resolve_place_names": True,
}, timeout=240)

# ---------- Analysis ----------
analysis = call("POST /api/analyze (coords)", "POST", "/api/analyze", {
    "origin": {"latitude": 12.9716, "longitude": 77.5946},
    "destination": {"latitude": 12.9784, "longitude": 77.6408},
}, timeout=600)

analysis_id = None
if isinstance(analysis, dict):
    analysis_id = analysis.get("analysis_id") or analysis.get("id")

if analysis_id:
    call("GET /api/analyze/{id}", "GET", f"/api/analyze/{analysis_id}")
    call("GET hazards", "GET", f"/api/analysis/{analysis_id}/hazards")
    call("GET comparison", "GET", f"/api/analysis/{analysis_id}/comparison")
    call("GET explanation", "GET", f"/api/analysis/{analysis_id}/explanation")
else:
    RESULTS.append({"name": "GET /api/analyze/{id}", "pass": False,
                    "detail": "no analysis_id returned by POST /api/analyze"})

call("GET /api/analyze/does-not-exist", "GET", "/api/analyze/nope", expect=404)

# ---------- Facilities ----------
call("POST /api/facilities (location)", "POST", "/api/facilities", {
    "location": {"latitude": 12.9716, "longitude": 77.5946}, "radius_m": 1000,
}, timeout=120)
call("POST /api/facilities (missing location)", "POST", "/api/facilities", {}, expect=400)

print(json.dumps({"results": RESULTS,
                  "analysis_id": analysis_id,
                  "analysis_keys": list(analysis.keys()) if isinstance(analysis, dict) else None},
                 indent=2))
