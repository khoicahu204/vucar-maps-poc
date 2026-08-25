"""Adapter: Vietmap-compatible Matrix API backed by self-hosted Valhalla.

Drop-in cho `calculate_matrix_travel_times` của Inspection-Scheduling-System:
cùng request/response shape (`code`, `durations[][sec]`, `distances[][m]`).

Backend chỉ cần đổi base URL, cache (PR #407) giữ nguyên.

Run: uvicorn main:app --host 0.0.0.0 --port 8010
"""

import logging
import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VUCAR Maps Adapter", version="0.1.0")

VALHALLA_URL = os.getenv("VALHALLA_URL", "http://valhalla:8002")
COSTING = os.getenv("COSTING", "motor_scooter")  # motor_scooter = KĐV đi xe máy


class MatrixRequest(BaseModel):
    points: list[dict]  # [{lat, lng}] — index = point index
    sources: list[int]  # source indices (row)
    destinations: list[int]  # destination indices (col)
    costing: str | None = None  # override; default motor_scooter


@app.get("/health")
def health():
    return {"status": "ok", "valhalla": VALHALLA_URL}


@app.post("/matrix")
async def matrix(req: MatrixRequest):
    """Vietmap-compatible /matrix/v4 → Valhalla sources_to_targets.

    Response: {"code": "OK", "durations": [[sec]], "distances": [[m]]}
    durations[i][j] = sources[i] -> destinations[j].
    """
    if not req.points or not req.sources or not req.destinations:
        raise HTTPException(status_code=400, detail="points/sources/destinations required")

    # Resolve indices → coordinates
    try:
        sources = [{"lat": req.points[i]["lat"], "lon": req.points[i]["lng"]} for i in req.sources]
        targets = [{"lat": req.points[i]["lat"], "lon": req.points[i]["lng"]} for i in req.destinations]
    except (IndexError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"bad point index: {e}")

    payload = {
        "sources": sources,
        "targets": targets,
        "costing": req.costing or COSTING,
        "units": "km",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{VALHALLA_URL}/sources_to_targets", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error("valhalla error: %s", e)
        raise HTTPException(status_code=502, detail=f"valhalla unavailable: {e}")

    if data.get("sources_to_targets") is None:
        raise HTTPException(status_code=502, detail="valhalla returned no matrix")

    n_src, n_dst = len(sources), len(targets)
    durations = [[None] * n_dst for _ in range(n_src)]
    distances = [[None] * n_dst for _ in range(n_src)]
    for cell in data["sources_to_targets"]:
        i, j = cell["from_index"], cell["to_index"]
        # Valhalla time = seconds, distance = km (units=km) → meters
        if cell.get("time") is not None:
            durations[i][j] = int(cell["time"])
        if cell.get("distance") is not None:
            distances[i][j] = round(cell["distance"] * 1000.0)

    return {"code": "OK", "durations": durations, "distances": distances}


# ─── Google/Goong-compatible (cho việc repoint app sau này) ─────────────
class DistanceMatrixRequest(BaseModel):
    origins: list[str]  # "lat,lng"
    destinations: list[str]
    mode: str = "motor_scooter"


@app.post("/distancematrix/json")
async def distancematrix(req: DistanceMatrixRequest):
    points = []
    for s in req.origins + req.destinations:
        lat, lng = s.split(",")
        points.append({"lat": float(lat), "lng": float(lng)})
    n_orig = len(req.origins)
    result = await matrix(
        MatrixRequest(
            points=points,
            sources=list(range(n_orig)),
            destinations=list(range(n_orig, n_orig + len(req.destinations))),
            async_=req.mode,
        )
    )
    return {
        "destination_addresses": req.destinations,
        "origin_addresses": req.origins,
        "rows": [
            {
                "elements": [
                    {
                        "status": "OK",
                        "duration": {"value": result["durations"][i][j] or -1, "text": ""},
                        "distance": {"value": result["distances"][i][j] or -1, "text": ""},
                    }
                    for j in range(len(req.destinations))
                ]
            }
            for i in range(len(req.origins))
        ],
    }
