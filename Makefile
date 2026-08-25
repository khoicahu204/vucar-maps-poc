# ─── VUCAR Maps POC: Valhalla self-hosted matrix ─────────────────────────

OSM_URL?=https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
DATA_DIR := data/custom_files

.PHONY: help download-osm up down logs build-graph benchmark clean

help:
	@echo "Targets:"
	@echo "  make download-osm   tải vietnam-latest.osm.pbf (~1.2GB) vào data/"
	@echo "  make up             build + start Valhalla (graph build lần đầu) + adapter"
	@echo "  make down           dừng services"
	@echo "  make logs           log adapter + valhalla"
	@echo "  make benchmark      chạy so sánh Valhalla vs Vietmap (cần VIETMAP_API_KEY)"
	@echo "  make clean          xóa data/ (graph + OSM), để dựng lại từ đầu"

download-osm:
	mkdir -p $(DATA_DIR)
	@test -f $(DATA_DIR)/vietnam-latest.osm.pbf && echo "OSM đã có" || \
		(curl -L -o $(DATA_DIR)/vietnam-latest.osm.pbf $(OSM_URL) && echo "OK: tải xong")

up:
	cp -n .env.example .env || true
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100 adapter valhalla

# Valhalla image tự build graph lần chạy đầu (10-30 phút, cần ~4-6GB RAM).
# Chạy benchmark sau khi graph xong (healthcheck OK).
benchmark: up
	@test -n "$$VIETMAP_API_KEY" || echo "set VIETMAP_API_KEY để so sánh với Vietmap"
	python3 benchmark/benchmark_matrix.py

consumer:
	@echo "Test nhanh 1 cặp qua adapter:"
	@curl -s -X POST http://localhost:8010/matrix -H 'Content-Type: application/json' \
		-d '{"points":[{"lat":10.74452,"lng":106.70212},{"lat":10.77584,"lng":106.70070}],"sources":[0],"destinations":[1]}' | python3 -m json.tool
