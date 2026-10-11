"""
JalRakshak AI — FastAPI backend backed by Amazon DynamoDB.

Endpoints (all under /api):
  GET  /api/health                      -> connectivity check against DynamoDB
  GET  /api/districts?state=punjab      -> district metadata list
  GET  /api/groundwater/latest          -> latest-week depth for every district
  GET  /api/groundwater/{district}      -> full 41-week series for one district
  POST /api/groundwater/{district}      -> write a new weekly reading (body: {week, date?, depthBgl})

Run (dev):   uvicorn app:app --reload --port 8001
Run (prod):  uvicorn app:app --host 0.0.0.0 --port 8001
"""
import math
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import get_backend, BACKEND

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

LATEST_WEEK = int(os.getenv("LATEST_WEEK", "41"))

_db = get_backend()          # dynamodb OR mysql (RDS), per DB_BACKEND in .env

app = FastAPI(title="JalRakshak AI API", version="1.0.0")

# The dashboard is opened from file:// or any host — allow all origins for now.
# Lock this down to your CloudFront/S3 bucket origin before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def stress_level(depth: float) -> dict:
    """Mirror of GroundwaterDataService.getStressLevel in index.html."""
    if depth > 30:
        return {"level": "high", "color": "#ef4444", "label": "High / Critical", "statusLabel": "Over-Exploited"}
    if depth >= 20:
        return {"level": "elevated", "color": "#f59e0b", "label": "Elevated", "statusLabel": "Critical"}
    return {"level": "normal", "color": "#10b981", "label": "Normal", "statusLabel": "Semi-Critical"}


def depletion_velocity(series: list, last_n: int = 8) -> float:
    li = len(series) - 1
    si = max(0, li - last_n + 1)
    return round((series[li]["depth"] - series[si]["depth"]) / last_n, 2)


def fetch_series(district: str) -> list:
    return _db.get_series(district)


@app.get("/api/health")
def health():
    try:
        info = _db.health()
        info["backend"] = BACKEND
        return {"status": "ok", **info}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"{BACKEND} database unreachable: {e}")


@app.get("/api/districts")
def districts(state: Optional[str] = None):
    out = [{
        "name": m["district"], "state": m["state"], "lat": m["lat"],
        "lng": m["lng"], "farms": m["farms"], "baseDepth": m["baseDepth"],
    } for m in _db.list_districts(state)]
    return {"count": len(out), "districts": sorted(out, key=lambda d: d["name"])}


@app.get("/api/groundwater/latest")
def latest():
    """One row per district with latest depth, stress, velocity — powers the map & priority table."""
    metas = {m["district"]: m for m in _db.list_districts()}
    rows = []
    for d, m in metas.items():
        series = fetch_series(d)
        if not series:
            continue
        depth = series[-1]["depth"]
        vel = depletion_velocity(series)
        stress = stress_level(depth)
        base_factor = 8 + (depth / 30) * 12
        mult = 1.4 if stress["level"] == "high" else 1.15 if stress["level"] == "elevated" else 1.0
        rows.append({
            "name": d,
            "state": m["state"],
            "lat": m["lat"],
            "lng": m["lng"],
            "farms": m["farms"],
            "depth": depth,
            "stress": stress,
            "velocity": vel,
            "extraction": round(base_factor * mult * 10),
            "projectedDepth8w": round(depth + vel * 8, 2),
        })
    rows.sort(key=lambda r: r["depth"], reverse=True)
    return {"week": LATEST_WEEK, "count": len(rows), "districts": rows}


@app.get("/api/groundwater/{district}")
def groundwater_one(district: str):
    all_metas = {m["district"]: m for m in _db.list_districts()}
    metas = all_metas.get(district)
    if not metas:
        raise HTTPException(status_code=404, detail=f"Unknown district: {district}")
    series = fetch_series(district)
    if not series:
        raise HTTPException(status_code=404, detail=f"No weekly data for: {district}")
    depth = series[-1]["depth"]
    return {
        "district": district,
        "meta": metas,
        "latest": series[-1],
        "stress": stress_level(depth),
        "velocity": depletion_velocity(series),
        "series": series,
    }


class Reading(BaseModel):
    week: int
    date: Optional[str] = None
    depthBgl: float


@app.post("/api/groundwater/{district}")
def put_reading(district: str, reading: Reading):
    if district not in {m["district"] for m in _db.list_districts()}:
        raise HTTPException(status_code=404, detail=f"Unknown district: {district}")
    _db.put_reading(district, reading.week, reading.date, reading.depthBgl)
    return {"ok": True, "item": {"district": district, "week": reading.week,
                                 "date": reading.date or "", "depthBgl": reading.depthBgl}}
