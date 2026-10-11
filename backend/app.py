"""
JalRakshak AI — Production-ready FastAPI Backend.

Supported Backends (selected via DB_BACKEND in .env or default: sqlite):
  - SQLite (zero configuration, default local file jalrakshak.db)
  - Amazon RDS MySQL
  - Amazon DynamoDB

Features:
  - Auto-initialization & auto-seeding on startup
  - Serves index.html and static assets directly at http://localhost:8001/
  - District groundwater monitoring & 41-week historical telemetry
  - Farm Registry CRUD with database persistence
  - Smart Tubewell remote monitoring & pump toggle control
  - Irrigation budget planner & calculation engine
  - Water budget threshold & notification settings persistence

Run:
  python app.py                      (or: uvicorn app:app --port 8001 --reload)
"""
import math
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from db import get_backend, BACKEND
from seed_data import seed_all

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

LATEST_WEEK = int(os.getenv("LATEST_WEEK", "41"))
_db = get_backend()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist and auto-seed if empty
    try:
        _db.init_schema()
        if _db.count_districts() == 0:
            print("[INFO] Database is unpopulated. Auto-seeding initial dataset...")
            seed_all(_db)
    except Exception as e:
        print(f"[WARN] Startup schema check: {e}")
    yield


app = FastAPI(
    title="JalRakshak AI API",
    version="2.0.0",
    description="Unified API & Database service for Groundwater Intelligence",
    lifespan=lifespan
)

# Enable CORS for external frontends or direct file:// access
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

INDEX_HTML_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "index.html")
)


# --------------------------------------------------------------------------
# Helper Logic
# --------------------------------------------------------------------------
def stress_level(depth: float) -> dict:
    if depth > 30:
        return {"level": "high", "color": "#ef4444", "dotClass": "red", "label": "High / Critical", "statusLabel": "Over-Exploited"}
    if depth >= 20:
        return {"level": "elevated", "color": "#f59e0b", "dotClass": "amber", "label": "Elevated", "statusLabel": "Critical"}
    return {"level": "normal", "color": "#10b981", "dotClass": "green", "label": "Normal", "statusLabel": "Semi-Critical"}


def depletion_velocity(series: list, last_n: int = 8) -> float:
    if not series or len(series) < 2:
        return 0.0
    li = len(series) - 1
    si = max(0, li - last_n + 1)
    span = max(1, li - si)
    return round((series[li]["depth"] - series[si]["depth"]) / span, 2)


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class ReadingInput(BaseModel):
    week: int = Field(..., ge=1, le=52)
    date: Optional[str] = None
    depthBgl: float = Field(..., ge=0.0)


class PlotInput(BaseModel):
    id: Optional[str] = None
    belt: Optional[str] = None
    district: str
    state: str
    owner: str
    acres: float
    crop: str
    stage: str
    center: Optional[List[float]] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    seed: Optional[int] = 10
    discharge: Optional[float] = 18.0
    runtime: Optional[float] = 6.0
    riskLevel: Optional[str] = "Normal"


class TubewellToggleInput(BaseModel):
    status: Optional[str] = None


class SettingsInput(BaseModel):
    threshold_normal: Optional[int] = 80
    threshold_watch: Optional[int] = 100
    threshold_high: Optional[int] = 120
    threshold_critical: Optional[int] = 150
    alert_email: Optional[bool] = True
    alert_sms: Optional[bool] = True
    alert_weekly_reports: Optional[bool] = True
    language: Optional[str] = "English"


# --------------------------------------------------------------------------
# Root / Frontend Route
# --------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    if os.path.exists(INDEX_HTML_PATH):
        return FileResponse(INDEX_HTML_PATH, media_type="text/html")
    return HTMLResponse("<h1>JalRakshak AI Backend API is running!</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>")


# --------------------------------------------------------------------------
# API Endpoints
# --------------------------------------------------------------------------
@app.get("/api/health")
def health():
    try:
        info = _db.health()
        info["backend"] = getattr(_db, "name", BACKEND)
        return {"status": "ok", **info}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unreachable: {e}")


@app.get("/api/districts")
def get_districts(state: Optional[str] = None):
    items = _db.list_districts(state)
    return {
        "count": len(items),
        "districts": sorted(items, key=lambda d: d["district"])
    }


@app.get("/api/groundwater/latest")
def get_latest_groundwater():
    metas = {m["district"]: m for m in _db.list_districts()}
    rows = []
    for d, m in metas.items():
        series = _db.get_series(d)
        if not series:
            continue
        depth = series[-1]["depth"]
        vel = depletion_velocity(series)
        stress = stress_level(depth)
        base_factor = 8 + (depth / 30.0) * 12
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
    return {
        "week": LATEST_WEEK,
        "count": len(rows),
        "districts": rows
    }


@app.get("/api/groundwater/{district}")
def get_groundwater_one(district: str):
    all_metas = {m["district"]: m for m in _db.list_districts()}
    meta = all_metas.get(district)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown district: {district}")
    series = _db.get_series(district)
    if not series:
        raise HTTPException(status_code=404, detail=f"No readings found for: {district}")
    depth = series[-1]["depth"]
    return {
        "district": district,
        "meta": meta,
        "latest": series[-1],
        "stress": stress_level(depth),
        "velocity": depletion_velocity(series),
        "series": series,
    }


@app.post("/api/groundwater/{district}")
def put_reading(district: str, reading: ReadingInput):
    known = {m["district"] for m in _db.list_districts()}
    if known and district not in known:
        raise HTTPException(status_code=404, detail=f"Unknown district: {district}")
    _db.put_reading(district, reading.week, reading.date, reading.depthBgl)
    return {
        "ok": True,
        "district": district,
        "item": {
            "week": reading.week,
            "date": reading.date or "",
            "depthBgl": reading.depthBgl
        }
    }


# --------------------------------------------------------------------------
# Farm Registry Endpoints
# --------------------------------------------------------------------------
@app.get("/api/registry/plots")
def get_plots(district: Optional[str] = None, state: Optional[str] = None):
    plots = _db.list_plots(district=district, state=state)
    return {"count": len(plots), "plots": plots}


@app.post("/api/registry/plots")
def create_plot(plot: PlotInput):
    plot_dict = plot.dict()
    if not plot_dict.get("id"):
        count = _db.count_plots() + 1
        prefix = (plot.district[:3] if plot.district else "PLT").upper()
        plot_dict["id"] = f"{prefix}-{count:02d}"
    if not plot_dict.get("belt"):
        plot_dict["belt"] = plot.district
    _db.upsert_plot(plot_dict)
    return {"ok": True, "plot": plot_dict}


@app.put("/api/registry/plots/{plot_id}")
def update_plot(plot_id: str, plot: PlotInput):
    plot_dict = plot.dict()
    plot_dict["id"] = plot_id
    _db.upsert_plot(plot_dict)
    return {"ok": True, "plot": plot_dict}


@app.delete("/api/registry/plots/{plot_id}")
def delete_plot(plot_id: str):
    success = _db.delete_plot(plot_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Plot not found: {plot_id}")
    return {"ok": True, "deleted": plot_id}


# --------------------------------------------------------------------------
# Tubewell & Pump Control Endpoints
# --------------------------------------------------------------------------
@app.get("/api/tubewells")
def get_tubewells():
    tws = _db.list_tubewells()
    return {"count": len(tws), "tubewells": tws}


@app.post("/api/tubewells/{tubewell_id}/toggle")
def toggle_tubewell(tubewell_id: str, body: Optional[TubewellToggleInput] = None):
    status_target = body.status if body else None
    result = _db.toggle_tubewell(tubewell_id, new_status=status_target)
    if not result:
        raise HTTPException(status_code=404, detail=f"Tubewell not found: {tubewell_id}")
    return {"ok": True, **result}


# --------------------------------------------------------------------------
# Irrigation Planner Endpoint
# --------------------------------------------------------------------------
@app.get("/api/planner/calculate")
def calculate_irrigation(
    crop: str = "Paddy",
    stage: str = "Mid-season",
    acres: float = 5.0,
    depth: float = 25.0,
    discharge: float = 18.0,
    soil_type: str = "Clay Loam"
):
    kc_table = {
        "Paddy": {"Initial": 0.60, "Development": 0.85, "Mid-season": 1.05, "Late": 0.85},
        "Wheat": {"Initial": 0.40, "Development": 0.75, "Mid-season": 1.10, "Late": 0.45},
        "Maize": {"Initial": 0.40, "Development": 0.75, "Mid-season": 1.15, "Late": 0.60},
        "Cotton": {"Initial": 0.35, "Development": 0.70, "Mid-season": 1.15, "Late": 0.70},
        "Sugarcane": {"Initial": 0.40, "Development": 0.75, "Mid-season": 1.25, "Late": 0.75}
    }
    kc = kc_table.get(crop, {}).get(stage, 0.90)
    base_et0 = 5.5
    etc = base_et0 * kc
    stress_mult = 1.3 if depth > 30 else 1.15 if depth >= 20 else 1.0
    net_req_mm = etc * stress_mult
    vol_cum = round((net_req_mm / 1000.0) * (acres * 4046.86), 1)
    optimal_runtime_hrs = round(vol_cum / max(1.0, discharge), 1)
    conventional_runtime_hrs = round(optimal_runtime_hrs * 1.35, 1)
    saved_cum = round((conventional_runtime_hrs - optimal_runtime_hrs) * discharge, 1)

    return {
        "crop": crop,
        "stage": stage,
        "acres": acres,
        "depthBgl": depth,
        "pumpCapacityM3h": discharge,
        "kc": kc,
        "waterRequirementM3": vol_cum,
        "recommendedRuntimeHours": optimal_runtime_hrs,
        "conventionalRuntimeHours": conventional_runtime_hrs,
        "dailyWaterSavingsM3": saved_cum,
        "recommendedFeederWindow": "Morning (05:00 AM - 09:00 AM)"
    }


# --------------------------------------------------------------------------
# Settings & Persistence Endpoints
# --------------------------------------------------------------------------
@app.get("/api/settings")
def get_settings():
    return _db.get_settings()


@app.post("/api/settings")
def save_settings(settings: SettingsInput):
    data = settings.dict()
    _db.save_settings(data)
    return {"ok": True, "settings": data}


@app.post("/api/database/seed")
def seed_database():
    seed_all(_db)
    return {"ok": True, "message": "Database successfully re-seeded and synchronized."}


# --------------------------------------------------------------------------
# Main Execution
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    print(f"Starting JalRakshak AI Backend on http://localhost:{port} (Database: {getattr(_db, 'name', BACKEND)})")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
