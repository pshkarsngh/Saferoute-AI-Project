"""Direct external-provider probe (no app code involved).

Separates 'provider unreachable' from 'our integration is broken'.
Reads MAPILLARY_ACCESS_TOKEN from .env only to test auth; never prints it.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "SafeRouteAI/1.0 (road-safety research)"
RESULTS = []


def load_env():
    env = {}
    p = ROOT / ".env"
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def req(name, method, url, data=None, headers=None, timeout=25):
    hdrs = {"User-Agent": UA}
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        hdrs["Content-Type"] = "application/json"
    started = time.time()
    try:
        r = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            ms = round((time.time() - started) * 1000)
            RESULTS.append({
                "provider": name, "ok": True, "status": resp.status, "ms": ms,
                "bytes": len(raw), "url": url,
                "preview": raw[:220].decode("utf-8", "replace"),
            })
    except urllib.error.HTTPError as e:
        ms = round((time.time() - started) * 1000)
        raw = e.read()[:300].decode("utf-8", "replace")
        RESULTS.append({"provider": name, "ok": False, "status": e.code, "ms": ms,
                        "error": f"HTTP {e.code}", "body": raw, "url": url})
    except Exception as e:  # noqa: BLE001
        ms = round((time.time() - started) * 1000)
        RESULTS.append({"provider": name, "ok": False, "status": None, "ms": ms,
                        "error": f"{type(e).__name__}: {e}", "url": url})


env = load_env()
token = env.get("MAPILLARY_ACCESS_TOKEN", "")

# 1. OSRM public demo (routing) — Bengaluru points
req("OSRM", "GET",
    "https://router.project-osrm.org/route/v1/driving/77.5946,12.9716;77.6408,12.9784"
    "?overview=false&alternatives=true")

# 2. Valhalla public demo (routing)
req("Valhalla", "GET",
    "https://valhalla1.openstreetmap.de/route?json=" +
    urllib.parse.quote(json.dumps({
        "locations": [{"lat": 12.9716, "lon": 77.5946}, {"lat": 12.9784, "lon": 77.6408}],
        "costing": "auto",
    })))

# 3. Nominatim (geocoding)
req("Nominatim", "GET",
    "https://nominatim.openstreetmap.org/search?q=Bengaluru&format=jsonv2&limit=1")

# 4. Overpass (facilities) — tiny bbox around central Bengaluru
overpass_q = "[out:json][timeout:25];node[amenity=hospital](12.96,77.58,12.98,77.61);out center 2;"
try:
    started = time.time()
    body = urllib.parse.urlencode({"data": overpass_q}).encode()
    r = urllib.request.Request("https://overpass-api.de/api/interpreter", data=body,
                               headers={"User-Agent": UA,
                                        "Content-Type": "application/x-www-form-urlencoded"},
                               method="POST")
    with urllib.request.urlopen(r, timeout=45) as resp:
        raw = resp.read()
        RESULTS.append({"provider": "Overpass", "ok": True, "status": resp.status,
                        "ms": round((time.time() - started) * 1000), "bytes": len(raw),
                        "preview": raw[:200].decode("utf-8", "replace")})
except Exception as e:  # noqa: BLE001
    RESULTS.append({"provider": "Overpass", "ok": False, "status": None,
                    "error": f"{type(e).__name__}: {e}", "url": "overpass-api.de"})

# 5. Mapillary (imagery) — token auth check
if token:
    req("Mapillary", "GET",
        "https://graph.mapillary.com/images?fields=id,captured_at&limit=1",
        headers={"Authorization": f"OAuth {token}"}, timeout=25)
else:
    RESULTS.append({"provider": "Mapillary", "ok": False, "status": None,
                    "error": "MAPILLARY_ACCESS_TOKEN not set in .env"})

# 6. Ollama (local LLM)
req("Ollama", "GET", "http://127.0.0.1:11434/api/tags", timeout=10)

print(json.dumps(RESULTS, indent=2))
