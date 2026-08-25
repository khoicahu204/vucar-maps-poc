# Vietmap Maps API — Self-hosted Alternative (POC)

> Thay thế Vietmap Matrix bằng engine self-hosted (Valhalla trên OpenStreetMap) để cắt chi phí theo transaction.

**Trạng thái:** POC / đề xuất — chưa production.
**Ngày:** 24/08/2026

---

## 1. Bối cảnh

- Hóa đơn Vietmap kỳ 14/06–13/08/2026: **477,098 transaction = 23,854,900 VNĐ**, trong đó **Matrix chiếm 431,107 (90%)**.
- Chi phí đang **tăng theo tốc độ** (13 ngày đầu tháng 8 = 202K elements, pace ~480K/tháng) do bot tự đặt lịch + khách tự đặt.
- PR #407 (cache vĩnh viễn) đã giảm volume, nhưng **vẫn phải trả 50đ/transaction** cho mọi element mới.

## 2. Mục tiêu

Self-host phần **Matrix** (90% chi phí) bằng engine open-source chạy trên OpenStreetMap, giữ chất lượng đủ tốt cho scheduling (thời gian di chuyển KĐV xe máy).

## 3. Lựa chọn engine

| Tiêu chí | **Valhalla** ✅ | OSRM | GraphHopper | MapTiler Server |
|---|---|---|---|---|
| Matrix API | ✅ `sources_to_targets` | ✅ Table | ✅ `/matrix` | ❌ **không có routing/matrix** (chỉ tile + geocode) |
| **Xe máy** (`motor_scooter`) | ✅ | ❌ | ⚠️ custom | — |
| Time-dependent (giờ cao điểm) | ✅ `date_time` | ❌ | ⚠️ | — |
| License | BSD-3 (free) | BSD-2 | Apache-2 | commercial |
| VN data | OSM (Geofabrik extract) | OSM | OSM | cloud |

**→ Valhalla: matrix API + `motor_scooter` (đúng KĐV đi xe máy) + free + time-dependent.**

> ⚠️ MapTiler Server (self-host) **không phủ được phần matrix** — chỉ tiles + geocoding. Nếu cần tile/map sau này thì dùng Martin + MapLibre (free) hoặc MapTiler Server.

## 4. Kiến trúc đề xuất

```
backend (Inspection-Scheduling) ── calculate_matrix_travel_times() ──┐
                                                                     ▼
                                                Adapter (FastAPI, container này)
                                                ┌──────────────────────────┐
                                                │  POST /matrix            │
                                                │  (Vietmap-compatible)    │
                                                └───────────┬──────────────┘
                                                            ▼
                                        Valhalla :8002 /sources_to_targets
                                        costing=motor_scooter, units=km
                                        data = vietnam-latest.osm.pbf
```

- **Adapter** giữ **đúng request/response contract** của `calculate_matrix_travel_times` → backend chỉ đổi base URL, **cache PR #407 vẫn dùng nguyên**.
- **Phase 2 (tùy chọn):** geocoder OSM (Photon) cho search/place — test chất lượng trước (rủi ro cao: địa chỉ số nhà/hẻm VN).

## 5. Chi phí

| | Vietmap (hiện tại) | Self-host Valhalla |
|---|---|---|
| Matrix | 50đ/transaction (~11M VNĐ/tháng, đang tăng) | **0đ/transaction** |
| Server | — | VPS 4GB RAM (~$30–50/tháng) |
| OSM data | Vietmap tự | Geofabrik VN extract (cập nhật định kỳ, miễn phí) |

**Tiết kiệm ~10–11M VNĐ/tháng từ Phase 1 (matrix).** Hoàn vốn < 1 tuần.

## 6. Rủi ro & giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| **OSM VN data kém hơn Vietmap** (số nhà, hẻm, tên đường) | 🔴 Cao | POC benchmark 100 địa chỉ thật vs Vietmap; chỉ swap matrix (tọa độ → tọa độ), giữ Vietmap cho geocode |
| `motor_scooter` time khác thực tế (giờ cao điểm HCMC) | 🟠 | Benchmark tuyến thật; chỉnh speed factor; cache vẫn làm trơn |
| Ops mới (build graph, update data) | 🟠 | Docker Compose sẵn; update định kỳ 1–3 tháng |
| ODbL attribution | 🟡 | Attribution trong app/README |

## 7. Kế hoạch

- [ ] **P0 — POC** (container này): dựng Valhalla VN graph + adapter + benchmark vs Vietmap
- [ ] **P1 — Validate**: benchmark 100+ tuyến thật (KĐV home → khách, khách → khách). Tiêu chí: % chênh ≤ 2 phút, không lệch hệ thống
- [ ] **P2 — Swich backend**: `calculate_matrix_travel_times` → adapter URL (đổi 1 hàm), giữ cache
- [ ] **P3 — (nếu cần) geocoder**: Photon test search/reverse VN
