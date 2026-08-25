# Kế hoạch thay thế Vietmap MATRIX bằng Valhalla self-hosted

**Ngày:** 25/08/2026 · **Trạng thái:** Đề xuất (sau POC) · **Repo POC:** `vucar-maps-poc`

---

## 1. Mục tiêu

Thay **Vietmap Matrix** (90% hóa đơn Maps API) bằng **Valhalla self-hosted** — GIỮ Vietmap cho phần **resolve/geocode** (địa chỉ → tọa độ, phần khó, OSM VN yếu).

**Lợi ích:** cắt ~90% chi phí matrix (≈10-11M VNĐ/tháng) → còn trả Vietmap phần geocode/search (~10% = ~1-2M VNĐ/tháng).

## 2. Kết quả POC (đã chứng minh)

| Chỉ số (100 route thật) | Giá trị | Đánh giá |
|---|---|---|
| Distance bias | +0.44 km | ✅ |
| Time raw bias | +14.2 phút | ❌ cần calibrate |
| **Time sau calibrate ×0.68** | **bias −2.4, \|Δ\| 5.7 phút, 67% trong ±5 phút** | ✅ chấp nhận được |
| NO_ROUTE | 2% (plus-code) | ⚠️ cần fallback |

→ Valhalla tìm **đúng đường, đúng km**; chỉ sai **giả định tốc độ** → calibrate giải quyết.

## 3. Kiến trúc

```
Inspection-Scheduling-System (backend)
│
├─ config: MATRIX_PROVIDER=vietmap|valhalla, VALHALLA_URL, MATRIX_TIME_FACTOR
│
├─ vietmap_service.calculate_matrix_travel_times()   ← ĐIỂM ĐỔI (giữ signature)
│   ├─ travel_cache (maplocations + moving_time)     ← GIỮ NGUYÊN (provider-agnostic)
│   └─ provider:
│       ├─ vietmap: gọi maps.vietmap.vn (hiện tại)
│       └─ valhalla: gọi Adapter /matrix  (Vietmap-compatible response)
│
└─ → Adapter (FastAPI, repo vucar-maps-poc/adapter)
       ├─ POST /matrix  (đúng format Vietmap: code/durations/distances)
       ├─ calibrate: ×0.68 (hoặc per road-class)
       └─ NO_ROUTE → trả null → backend fallback DEFAULT_TRAVEL_MINUTES
    → Valhalla (ghcr.io/valhalla/valhalla-scripted, costing=motor_scooter)
       → data: vietnam-latest.osm.pbf
```

**Không đổi:** available-slots, optimizer, check-availability, resolve-address (50km vẫn Vietmap), cache PR #407.

## 4. Các bước thực hiện

### Phase 1 — Code backend (2-3 ngày)
- [ ] Thêm `MATRIX_PROVIDER` config (env) + `VALHALLA_URL` + `MATRIX_TIME_FACTOR`
- [ ] Sửa `calculate_matrix_travel_times`: nếu provider=valhalla → gọi adapter, áp dụng factor, trả về **cùng response shape**
- [ ] Fallback: adapter trả `null` (NO_ROUTE) → giữ `DEFAULT_TRAVEL_MINUTES` (45') như hệ thống đang có
- [ ] Giữ cache PR #407 nguyên (tự động dùng chung)

### Phase 2 — Deploy Adapter + Valhalla (1 ngày)
- [ ] Deploy Adapter + Valhalla lên server (Docker Compose — đã có sẵn trong POC)
- [ ] Cập nhật OSM VN (Geofabrik) — khuyến nghị refresh hàng tháng
- [ ] Load test: 100 request/s matrix → đo latency (Valhalla ~50-200ms/request batched)

### Phase 3 — Chuyển đổi từ từ (an toàn)
- [ ] Deploy backend với `MATRIX_PROVIDER=vietmap` (mặc định) + shadow-log
- [ ] Chạy 1 tuần: so sánh cache hits + route Valhalla vs Vietmap trên log thật
- [ ] Đổi `MATRIX_PROVIDER=valhalla` — **giữ khả năng revert 1 env**

### Phase 4 — Giám sát (liên tục)
- [ ] Metric: tỷ lệ NO_ROUTE (mục tiêu <5%), latency, cache hit rate
- [ ] Recalibrate factor hàng tháng (so 100 route mẫu)
- [ ] Đối soát hóa đơn Vietmap kỳ sau → xác nhận giảm ~90%

## 5. Chi tiết code thay đổi (backend)

```python
# config.py thêm
MATRIX_PROVIDER = os.getenv("MATRIX_PROVIDER", "vietmap")  # vietmap | valhalla
VALHALLA_URL = os.getenv("VALHALLA_URL", "")
MATRIX_TIME_FACTOR = float(os.getenv("MATRIX_TIME_FACTOR", "0.68"))

# vietmap_service.calculate_matrix_travel_times():
#   - cache check (giữ nguyên)
#   - if provider == "valhalla": gọi adapter POST /matrix, ×MATRIX_TIME_FACTOR
#     (adapter đã trả đúng {code, durations, distances} — không đổi response parse)
#   - else: gọi Vietmap như cũ
# Fallback: durations[i][j]=null → caller dùng DEFAULT_TRAVEL_MINUTES (có sẵn)
```

## 6. Hạ tầng

| Hạng mục | Chi tiết | Chi phí ước tính |
|---|---|---|
| Server | VPS/VM 4 vCPU / 8GB RAM (đã có POC trên OVH SGP1) | $30-50/tháng |
| OSM data | Geofabrik VN extract (312MB) + refresh định kỳ | 0đ |
| Adapter | FastAPI, container nhỏ | 0đ |
| **So với Vietmap matrix** | ~10-11M VNĐ/tháng đang trả | **tiết kiệm ~90%** |

## 7. Rủi ro & giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| NO_ROUTE (plus-code / OSM thiếu hẻm) | 🟠 2% | Fallback DEFAULT_TRAVEL_MINUTES (đã có) + flag để theo dõi |
| Calibrate lệch theo thời gian | 🟡 | Recalibrate hàng tháng (script có sẵn) |
| OSM data cũ | 🟡 | Refresh Geofabrik hàng tháng |
| Latency (SGP1 ~30-50ms) | 🟢 | Cache PR #407 đã che chắn phần lớn |
| Valhalla down | 🟢 | Provider switch 1 env → về Vietmap |

## 8. Timeline ước tính

| Tuần | Việc |
|---|---|
| W1 | Phase 1 (code backend + fallback) + Phase 2 (deploy adapter) |
| W2 | Phase 3 (shadow 1 tuần → bật valhalla) |
| W3+ | Phase 4 (giám sát + recalibrate) — đối soát hóa đơn đầu tháng sau |

## 9. Quyết định cần team
- [ ] Chốt giữ Vietmap cho resolve/geocode (chi phí còn ~1-2M VNĐ/tháng)
- [ ] Chốt calibrate đơn giản ×0.68 trước, tune per road-class sau nếu cần
- [ ] Server chạy Valhalla: OVH SGP1 (đang chạy POC) hay server VUCAR có sẵn?
