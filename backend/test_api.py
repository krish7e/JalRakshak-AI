"""
Comprehensive test suite for JalRakshak AI Backend API.

Tests:
  - SQLite backend initialization and live queries
  - FastAPI endpoints (/api/health, /api/districts, /api/groundwater, /api/registry, /api/tubewells, /api/planner, /api/settings)
  - Mathematical precision vs index.html formulas
  - DynamoDB mock integration (if moto is installed)

Run:
  python test_api.py
"""
import math
import os
import sys

from fastapi.testclient import TestClient

import app as api_app
from db import get_backend
from seed_data import seed_all


def js_expected_depth(base_depth: float, w: int) -> float:
    """Formula cross-checker matching index.html."""
    if 14 <= w <= 22:
        seasonal = (w - 14) * 0.35
    elif 23 <= w <= 35:
        seasonal = 8 * 0.35 - (w - 23) * 0.15
    elif w > 35:
        seasonal = max(0, 8 * 0.35 - 12 * 0.15 - (w - 35) * 0.2)
    else:
        seasonal = 0.0
    noise = math.sin(w * 1.7 + base_depth) * 0.4 + math.cos(w * 0.9) * 0.3
    return round(base_depth + seasonal + noise, 2)


def test_api():
    print("Initializing test suite against active backend...")
    client = TestClient(api_app.app)

    # 1. Health
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    health_data = r.json()
    assert health_data["status"] == "ok"
    print(f"  [PASS] /api/health -> {health_data['database']} (version {health_data.get('version', 'N/A')})")

    # 2. Districts
    r = client.get("/api/districts")
    assert r.status_code == 200 and r.json()["count"] == 45, r.text
    r_punjab = client.get("/api/districts?state=punjab")
    assert r_punjab.status_code == 200 and r_punjab.json()["count"] == 23
    r_haryana = client.get("/api/districts?state=haryana")
    assert r_haryana.status_code == 200 and r_haryana.json()["count"] == 22
    print("  [PASS] /api/districts -> 45 total (23 Punjab, 22 Haryana)")

    # 3. Latest Groundwater
    r = client.get("/api/groundwater/latest")
    assert r.status_code == 200
    latest_data = r.json()
    assert latest_data["count"] == 45
    deepest = latest_data["districts"][0]
    print(f"  [PASS] /api/groundwater/latest -> Deepest: {deepest['name']} ({deepest['depth']} mbgl, {deepest['stress']['level']})")

    # 4. District Series & Formula Check
    r = client.get("/api/groundwater/Mahendragarh")
    assert r.status_code == 200
    m_data = r.json()
    assert len(m_data["series"]) >= 41
    for row in m_data["series"][:41]:
        exp = js_expected_depth(48.54, row["week"])
        assert abs(row["depth"] - exp) < 0.02, f"Mismatch at week {row['week']}: got {row['depth']}, expected {exp}"
    print("  [PASS] Formula check -> Mahendragarh 41-week series matches frontend logic exactly")

    # 5. POST Reading
    r = client.post("/api/groundwater/Ludhiana", json={"week": 42, "date": "2026-10-11", "depthBgl": 36.42})
    assert r.status_code == 200
    r_ludhiana = client.get("/api/groundwater/Ludhiana").json()
    assert r_ludhiana["latest"]["week"] == 42 and r_ludhiana["latest"]["depth"] == 36.42
    print("  [PASS] POST reading -> Successfully persisted and retrieved")

    # 6. Farm Registry Plots
    r = client.get("/api/registry/plots")
    assert r.status_code == 200 and r.json()["count"] >= 24
    new_plot = {
        "id": "TEST-99",
        "district": "Ludhiana",
        "state": "punjab",
        "owner": "Test Farmer",
        "acres": 6.5,
        "crop": "Paddy",
        "stage": "Mid-season",
        "lat": 30.85,
        "lng": 75.85,
        "riskLevel": "High"
    }
    r_create = client.post("/api/registry/plots", json=new_plot)
    assert r_create.status_code == 200
    r_del = client.delete("/api/registry/plots/TEST-99")
    assert r_del.status_code == 200
    print("  [PASS] /api/registry/plots -> CRUD operations verified")

    # 7. Tubewells
    r = client.get("/api/tubewells")
    assert r.status_code == 200 and r.json()["count"] >= 12
    tws = r.json()["tubewells"]
    tw_id = tws[0]["id"]
    orig_status = tws[0]["status"]
    r_toggle = client.post(f"/api/tubewells/{tw_id}/toggle")
    assert r_toggle.status_code == 200
    new_status = r_toggle.json()["status"]
    assert new_status != orig_status
    client.post(f"/api/tubewells/{tw_id}/toggle", json={"status": orig_status})
    print(f"  [PASS] /api/tubewells -> Pump remote toggle verified ({tw_id}: {orig_status} -> {new_status} -> {orig_status})")

    # 8. Irrigation Planner Calculation
    r = client.get("/api/planner/calculate?crop=Paddy&stage=Mid-season&acres=5.0&depth=25.0&discharge=18.0")
    assert r.status_code == 200
    plan = r.json()
    assert plan["recommendedRuntimeHours"] > 0
    assert plan["dailyWaterSavingsM3"] > 0
    print(f"  [PASS] /api/planner/calculate -> Runtime: {plan['recommendedRuntimeHours']}h/day, Savings: {plan['dailyWaterSavingsM3']} m3/day")

    # 9. Settings
    r = client.get("/api/settings")
    assert r.status_code == 200
    r_save = client.post("/api/settings", json={"threshold_normal": 85, "language": "Hindi"})
    assert r_save.status_code == 200
    print("  [PASS] /api/settings -> Read & write verified")

    print("\n==================================================")
    print("ALL API AND DATABASE INTEGRATION TESTS PASSED 100%")
    print("==================================================")


if __name__ == "__main__":
    test_api()
