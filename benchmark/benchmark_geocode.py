#!/usr/bin/env python3
"""Geocode test: cùng 1 địa chỉ text → Nominatim(OSM) vs tọa độ Vietmap đang lưu.

Cách dùng: python3 benchmark_geocode.py [--locs movingtime_100locs.json] [--limit 100]
Output: % khớp trong 100m/500m/1km/5km + |mean Δ|.
"""
import argparse, json, math, statistics, time, urllib.parse, urllib.request, urllib.error

NOMINATIM = "http://15.235.202.74:8080"  # mediagis/nominatim trên VM

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

def geocode(address):
    q = urllib.parse.quote(address)
    url = f"{NOMINATIM}/search?q={q}&format=json&limit=1&countrycodes=vn&accept-language=vi"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            d = json.load(r)
        if d:
            return float(d[0]["lat"]), float(d[0]["lon"]), d[0].get("display_name","")[:60]
    except Exception:
        pass
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--locs", default="benchmark/movingtime_100locs.json")
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()
    locs = json.load(open(args.locs))[:args.limit]

    print(f"{'địa chỉ':<46} {'VM':>12} {'OSM':>12} {'Δ(m)':>8}")
    print("-" * 82)
    dists, fails = [], 0
    for l in locs:
        addr = l["address"]
        r = geocode(addr)
        if r is None:
            fails += 1
            print(f"{addr[:44]:<46} {'—':>12} {'FAIL':>12}")
            continue
        d = haversine(l["lat"], l["lng"], r[0], r[1])
        dists.append(d)
        mark = "✓" if d <= 500 else ("⚠️" if d <= 2000 else "✗")
        print(f"{addr[:44]:<46} {l['lat']:.5f},{l['lng']:.5f} {r[0]:.5f},{r[1]:.5f} {d:>7.0f} {mark}")
        time.sleep(0.3)  # tránh rate limit

    if dists:
        print("-" * 82)
        n = len(dists)
        print(f"n={n}  FAIL={fails}")
        for th in (100, 500, 1000, 2000, 5000):
            pct = sum(1 for d in dists if d <= th) / n * 100
            print(f"  trong {th:>5}m: {pct:.0f}%")
        print(f"  |mean Δ| = {statistics.mean(dists):.0f} m   median = {statistics.median(dists):.0f} m")

if __name__ == "__main__":
    main()
