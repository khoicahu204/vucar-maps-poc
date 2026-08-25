#!/usr/bin/env python3
"""So sánh QUÃNG ĐƯỜNG (distance) Valhalla vs Vietmap trên 500 maplocation thật.

Cách dùng: VIETMAP_API_KEY=... VALHALLA_URL=... python3 benchmark_distance.py
- 80 tuyến: office(Thủ Đức) → địa điểm ngẫu nhiên trong 500 + 40 cặp ngẫu nhiên
- So sánh distance (km) + duration (min), report bias + % lệch.
"""
import json, os, random, statistics, sys, urllib.request

KEY = os.getenv("VIETMAP_API_KEY", "")
VH = os.getenv("VALHALLA_URL", "http://localhost:8010")
OFFICE = (10.777761, 106.754709)  # Dreamplex Lê Hiến Mai (Nam office)

locs = json.load(open("benchmark/maplocations_500.json"))
random.seed(42)

def vm_dist(points):
    parts = [f"point={p[0]},{p[1]}" for p in points]
    qs = "&".join([f"apikey={KEY}", "annotation=duration;distance", "vehicle=motorcycle", *parts,
                   "sources=0", "destinations=1"])
    with urllib.request.urlopen(f"https://maps.vietmap.vn/api/matrix/v4?{qs}", timeout=20) as r:
        return json.load(r)

def vh_dist(points):
    body = json.dumps({"points": [{"lat": p[0], "lng": p[1]} for p in points],
                       "sources": [0], "destinations": [1]}).encode()
    req = urllib.request.Request(f"{VH}/matrix", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

# pairs: office -> 40 random + 40 random pairs
pairs = [(OFFICE, (l["lat"], l["lng"]), f"office->{l['address'][:20]}") for l in random.sample(locs, 40)]
pool = random.sample(locs, 40)
for a, b in zip(pool[::2], pool[1::2]):
    pairs.append(((a["lat"], a["lng"]), (b["lat"], b["lng"]), f"{a['address'][:14]}->{b['address'][:14]}"))

print(f"{'tuyến':<44} {'VM km':>8} {'VH km':>8} {'Δkm':>7} {'VM min':>7} {'VH min':>7} {'Δmin':>7}")
print("-" * 95)
d_d, d_t = [], []
no_route = 0
for p1, p2, name in pairs:
    try:
        vm = vm_dist([p1, p2])["durations"][0][0], vm_dist([p1, p2])["distances"][0][0]
    except Exception as e:
        vm = None
    try:
        vh = vh_dist([p1, p2])
        vh_t = vh["durations"][0][0] / 60
        vh_d = vh["distances"][0][0] / 1000
    except Exception:
        vh = None
    if vh is None or vh_t is None:
        no_route += 1
        print(f"{name:<44} {'—':>8} {'NO_ROUTE':>8}")
        continue
    if vm is None:
        print(f"{name:<44} {'ERR':>8} {vh_d:>8.1f}")
        continue
    vm_d, vm_t = vm[1] / 1000, vm[0] / 60
    d_d.append(vh_d - vm_d); d_t.append(vh_t - vm_t)
    print(f"{name:<44} {vm_d:>8.1f} {vh_d:>8.1f} {vh_d-vm_d:>+7.1f} {vm_t:>7.1f} {vh_t:>7.1f} {vh_t-vm_t:>+7.1f}")

print("-" * 95)
print(f"n={len(d_d)}  NO_ROUTE={no_route}")
print(f"DISTANCE: |mean Δ|={statistics.mean(abs(d) for d in d_d):.2f} km  bias={statistics.mean(d_d):+.2f} km  "
      f"% lệch≤10%={sum(1 for i,d in enumerate(d_d) if abs(d)/vm_d<=0.10)/len(d_d)*100:.0f}%")
print(f"TIME:     |mean Δ|={statistics.mean(abs(d) for d in d_t):.1f} phút  bias={statistics.mean(d_t):+.1f} phút")
