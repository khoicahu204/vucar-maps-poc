# Kết quả POC Valhalla vs Vietmap — 25/08/2026

## Setup
- VM: OVH huy-dev, SGP1, d2-4 (4 vCPU/8GB), Ubuntu 24.04, IP 15.235.202.74
- Valhalla: `ghcr.io/valhalla/valhalla-scripted:latest` (3.8.3), graph từ `vietnam-latest.osm.pbf` (Geofabrik, 312MB)
- Adapter: `/matrix` (Vietmap-compatible) — drop-in cho `calculate_matrix_travel_times`
- Data thật: 72 tuyến KĐV home → địa điểm khách (từ maplocations + bookings)

## Kết quả chính (72 tuyến thật)

| Chỉ số | Giá trị |
|---|---|
| |mean Δ| | **8.0 phút** |
| Trong ±2 phút | 4% |
| Trong ±5 phút | 26% |
| **Bias (VH − VM)** | **+7.9 phút** (Valhalla CHẬM HƠN đều) |
| NO_ROUTE (OSM thiếu đường) | vài tuyến (vd Q6→Q10) |

→ **Tiêu chí chấp nhận (≥70% trong ±2 phút) KHÔNG đạt với cấu hình mặc định.**

## Phân tích bias +7.9 phút

1. **`motor_scooter` default chậm** — speed theo road-class của OSM (residential ~25-30 km/h) thấp hơn xe máy VN thực tế. `top_speed=45→60` KHÔNG giúp (speed không bị cap). `fixed_speed=55/60` quá nhanh (13.3/12.3 vs Vietmap 18.9). `motorcycle` vẫn chậm (26.4).
2. → **Cần calibrate tốc độ** (custom speed profile / hệ số nhân) — POC cho thấy Valhalla ĐỦ khả năng khớp nhưng chưa đúng ngay.
3. **OSM VN còn lỗ hổng** (NO_ROUTE) — rủi ro thật với các tuyến qua Q6, vùng ven.

## Đánh giá cho bài toán VUCAR

- ⚠️ **Bias dương (chậm hơn) = an toàn nhưng mất capacity**: scheduling dùng buffer ×1.5; Valhalla chậm hơn đều → slot chắc chắn đủ thời gian nhưng **giảm số slot/ngày** (~20-30%).
- ⚠️ **PR #407 (cache) đã giảm volume matrix mạnh** → chi phí Vietmap tương lai thấp hơn nhiều → ROI của self-host đã đổi.
- ✅ **Valhalla vẫn là phương án backup khả thi**: chạy được end-to-end, tune được, chi phí 0đ/transaction.

## Quyết định cần team

1. **Đo lại hóa đơn Vietmap sau khi deploy PR #407** (1-2 tháng) → còn bao nhiêu $/tháng?
2. Nếu vẫn cao (vd >5M VNĐ/tháng) → đầu tư calibrate Valhalla (2-3 ngày): fit speed profile với 100+ tuyến thật, thêm fallback cho NO_ROUTE.
3. Nếu thấp → giữ Vietmap + cache (đơn giản, chất lượng data tốt hơn).

## Reproduce
```bash
# benchmark 72 tuyến thật (từ máy có key Vietmap)
VIETMAP_API_KEY=... VALHALLA_URL=http://15.235.202.74:8010 \
  python3 benchmark/benchmark_matrix.py --pairs benchmark/pairs_real.json
```

## Bổ sung 25/08 — Test 500 maplocation thật (60 tuyến ngẫu nhiên)

| Chỉ số | DISTANCE (km) | TIME (phút) |
|---|---|---|
| |mean Δ| | 1.70 km | **12.7 phút** |
| bias (VH−VM) | +0.64 km | **+12.7 phút** |
| % lệch ≤10% | 57% | — |
| **NO_ROUTE** | **20/60 = 33%** ⚠️⚠️ | |

**Kết luận quan trọng:**
1. ✅ **Khoảng cách OK** — Valhalla tính distance khá sát Vietmap (bias +0.6km, 57% lệch ≤10%).
2. ❌ **Thời gian lệch hệ thống +8→+13 phút** — do speed profile thấp hơn xe máy VN thực tế (cần calibrate, chưa đạt tiêu chí).
3. ❌❌ **NO_ROUTE = 33%** — Valhalla không route được ~1/3 tuyến thật (plus-code/vùng OSM thiếu đường/snap fail). Đây là rào cản lớn nhất cho scheduling (không tính được travel = không validate được slot).

→ **Valhalla/OSM hiện CHƯA thay thế được Vietmap cho scheduling** (distance ok nhưng time bias + NO_ROUTE quá cao). Giữ Vietmap + cache (PR #407) là hướng khả thi nhất hiện tại.

Test geocode (address→coords) chưa chạy — cần build Nominatim/Photon VN (~1-2h) — kết quả routing cho thấy OSM VN còn lỗ hổng, nên cân nhắc trước khi đầu tư thời gian.
