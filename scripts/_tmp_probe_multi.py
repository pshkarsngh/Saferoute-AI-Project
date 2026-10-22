"""Temporary probe: composed routing provider over the live services."""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.routing.adapter import create_routing_adapter
from src.routing.schemas import Coordinate, RouteRequest
from src.routing.multi_adapter import corridor_overlap

adapter = create_routing_adapter("multi")
print("provider:", adapter.provider_name, adapter.provider_names)

req = RouteRequest(
    origin=Coordinate(latitude=12.9698, longitude=77.7504),
    destination=Coordinate(latitude=12.9716, longitude=77.5946),
)
t0 = time.perf_counter()
resp = adapter.get_routes(req)
print(f"elapsed={time.perf_counter()-t0:.2f}s status={resp.status.value} providers={resp.providers}")
print("limitations:", resp.limitations)
for r in resp.routes:
    print(f"  {r.route_id} | {r.provider} | {r.summary} | {r.distance_m/1000:.2f}km | {r.duration_s/60:.1f}min | segs={len(r.segments)} | pts={len(r.geometry.coordinates)}")

print("\npairwise corridor overlap:")
for i, a in enumerate(resp.routes):
    for j, b in enumerate(resp.routes):
        if i < j:
            ov = corridor_overlap(a.geometry.coordinates, b.geometry.coordinates)
            print(f"  {a.route_id} vs {b.route_id}: {ov:.3f}")

# raw per-provider route counts (no merge)
for name in ("osrm", "valhalla"):
    sub = create_routing_adapter(name)
    r = sub.get_routes(req)
    print(f"\n{name}: status={r.status.value} routes={len(r.routes)}")
    for x in r.routes:
        print(f"   {x.route_id} | {x.summary} | {x.distance_m/1000:.2f}km")
