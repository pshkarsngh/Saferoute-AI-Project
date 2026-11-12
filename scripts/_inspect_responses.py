"""Inspect the substance of the responses produced by _check_endpoints.py."""
import json
import sqlite3
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read())


analysis_id = "an-641a993fa3b2"
rec = get(f"/api/analyze/{analysis_id}")

print("=" * 70)
print("ANALYSIS", analysis_id)
print("status                :", rec.get("status"))
print("provider(s)           :", rec.get("provider"), "|", rec.get("providers"))
print("model_version         :", rec.get("model_version"))
print("model_status          :", rec.get("model_status"))
print("detection_validated   :", rec.get("detection_validated"))
print("origin_resolution     :", rec.get("origin_resolution"))
print("destination_resolution:", rec.get("destination_resolution"))
print("routes returned       :", len(rec.get("routes", [])))
print("recommendation        :", json.dumps(rec.get("recommendation"))[:400])
print("limitations           :", json.dumps(rec.get("limitations"))[:500])
print("timings_ms            :", json.dumps(rec.get("timings_ms"))[:300])
print("detection_validation  :", json.dumps(rec.get("detection_validation"))[:400])

for route in rec.get("routes", []):
    print("-" * 70)
    print("route_id              :", route.get("route_id"))
    print("provider              :", route.get("provider"))
    print("distance_m/duration_s :", route.get("distance_m"), route.get("duration_s"))
    print("score                 :", route.get("safety_score"), "| status:", route.get("status"))
    print("coverage              :", json.dumps(route.get("coverage"))[:300])
    segs = route.get("segments", [])
    print("segments              :", len(segs))
    if segs:
        assessed = [s for s in segs if s.get("status") == "assessed"]
        print("  assessed segments   :", len(assessed))
        print("  segment sample keys :", sorted(segs[0].keys()))
    hazards = route.get("hazards", [])
    print("hazards               :", len(hazards), json.dumps(hazards[:2])[:300])

print("=" * 70)
expl = get(f"/api/analysis/{analysis_id}/explanation")
print("EXPLANATION keys:", list(expl.keys()))
print(json.dumps(expl, indent=2)[:1500])

print("=" * 70)
comp = get(f"/api/analysis/{analysis_id}/comparison")
print("COMPARISON:", json.dumps(comp, indent=2)[:1200])

print("=" * 70)
fac = None
req = urllib.request.Request(
    BASE + "/api/facilities",
    data=json.dumps({"location": {"latitude": 12.9716, "longitude": 77.5946},
                     "radius_m": 1000}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=120) as r:
    fac = json.loads(r.read())
print("FACILITIES keys:", list(fac.keys()))
print("status/provider :", fac.get("status"), "|", fac.get("provider"), "|", fac.get("source"))
print("counts          :", json.dumps(fac.get("counts") or fac.get("category_counts"))[:400])
print("limitations     :", json.dumps(fac.get("limitations"))[:400])
print(json.dumps(fac, indent=2)[:1200])

print("=" * 70)
db = ROOT / "data" / "saferoute.db"
con = sqlite3.connect(db)
cur = con.cursor()
tables = [r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("SQLITE tables:", tables)
for t in tables:
    n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t:<22} rows={n}")
con.close()
