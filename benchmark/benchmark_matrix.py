#!/usr/bin/env python3
"""Benchmark: Valhalla (self-hosted) vs Vietmap Matrix trên các tuyến Việt Nam.

Cách dùng:
  VIETMAP_API_KEY=... VALHALLA_URL=http://localhost:8010 \
      python3 benchmark_matrix.py [--pairs pairs.json] [--limit 50]

Không có --pairs: dùng 10 tuyến mẫu HCMC (KĐV home → địa điểm khách).
Output: so sánh duration_minutes từng tuyến + summary (độ lệch, % khớp).
"""

import argparse
import json
import os
import statistics
import urllib.request

VIETMAP_KEY = os.getenv("VIETMAP_API_KEY", "")
VIETMAP_MATRIX_URL = "https://maps.vietmap.vn/api/matrix/v4"
VALHALLA_URL = os.getenv("VALHALLA_URL", "http://localhost:8010")

# Mẫu: KĐV home (Q7, Gò Vấp, Thủ Đức...) → địa điểm khách (Q1, Q2, Bình Thạnh...)
SAMPLE_PAIRS = [
    # (name, lat1, lng1, lat2, lng2)
    ("Q7 -> Q1", 10.74452, 106.70212, 10.77584, 106.70070),
    ("Q7 -> Q2", 10.74452, 106.70212, 10.78120, 106.72824),
    ("GV -> Q3", 10.82513, 106.67425, 10.78445, 106.68772),
    ("TD -> Q9", 10.85851, 106.76195, 10.84247, 106.77108),
    ("Q8 -> Q5", 10.72713, 106.64957, 10.75543, 106.66724),
    ("BT -> Q1", 10.80333, 106.70587, 10.77579, 106.70022),
    ("Q4 -> Q7", 10.76360, 106.70500, 10.74445, 106.70212),
    ("TN -> TD", 10.86510, 106.70902, 10.85851, 106.76195),
    ("Q6 -> Q10", 10.75135, 106.64373, 10.77057, 106.66653),
    ("QL50 -> Q1", 10.76243, 106.67202, 10.77579, 106.70022),
]


def vietmap_matrix(points, sources, dests):
    """Call Vietmap matrix — same contract as calculate_matrix_travel_times."""
    parts = [f"point={p[0]},{p[1]}" for p in points]
    qs = "&".join(
        [
            f"apikey={VIETMAP_KEY}",
            "annotation=duration;distance",
            "vehicle=motorcycle",
            *parts,
            f"sources={';'.join(map(str, sources))}",
            f"destinations={';'.join(map(str, dests))}",
        ]
    )
    with urllib.request.urlopen(f"{VIETMAP_MATRIX_URL}?{qs}", timeout=20) as r:
        return json.load(r)


def valhalla_matrix(points, sources, dests):
    body = json.dumps(
        {
            "points": [{"lat": p[0], "lng": p[1]} for p in points],
            "sources": sources,
            "destinations": dests,
        }
    ).encode()
    req = urllib.request.Request(
        f"{VALHALLA_URL}/matrix", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", help="JSON file: [[name, lat1, lng1, lat2, lng2], ...]")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    pairs = SAMPLE_PAIRS
    if args.pairs:
        with open(args.pairs) as f:
            pairs = [tuple(x) for x in json.load(f)]
    if args.limit:
        pairs = pairs[: args.limit]

    if not VIETMAP_KEY:
        print("⚠️  VIETMAP_API_KEY chưa set — chỉ chạy Valhalla (bỏ qua so sánh).")

    print(f"{'Tuyến':<38} {'VM(min)':>9} {'VH(min)':>9} {'Δ(min)':>9}   ghi chú")
    print("-" * 66)
    diffs = []
    for name, la1, lo1, la2, lo2 in pairs:
        points = [(la1, lo1), (la2, lo2)]
        vh_min = None
        try:
            vh = valhalla_matrix(points, [0], [1])
            vh_sec = vh["durations"][0][0]
            vh_min = vh_sec / 60 if vh_sec else None
        except Exception as e:
            print(f"{name:<38} {'—':>10} {'ERR':>10} {'—':>9}   {e}")
            continue

        vm_min = None
        if VIETMAP_KEY:
            try:
                vm = vietmap_matrix(points, [0], [1])
                vm_sec = vm["durations"][0][0]
                vm_min = vm_sec / 60 if vm_sec else None
            except Exception as e:
                print(f"{name:<38} {'ERR':>10} {vh_min:>10.1f} {'—':>9}   vietmap: {e}")

        if vh_min is not None and vm_min is not None:
            d = vh_min - vm_min
            diffs.append(d)
            note = "✓" if abs(d) <= 2 else ("⚠️" if abs(d) <= 5 else "✗")
            print(f"{name:<38} {vm_min:>10.1f} {vh_min:>10.1f} {d:>+9.1f}   {note}")
        else:
            print(f"{name:<38} {'—':>10} {vh_min:>10.1f} {'—':>9}   (chỉ Valhalla)")

    if diffs:
        print("-" * 66)
        print(f"n={len(diffs)}  |mean Δ|= {statistics.mean(abs(d) for d in diffs):.1f} phút")
        within2 = sum(1 for d in diffs if abs(d) <= 2) / len(diffs) * 100
        within5 = sum(1 for d in diffs if abs(d) <= 5) / len(diffs) * 100
        print(f"Trong ±2 phút: {within2:.0f}%   Trong ±5 phút: {within5:.0f}%")
        print(f"Bias (VH - VM): {statistics.mean(diffs):+.1f} phút")


if __name__ == "__main__":
    main()
