"""
Seed script for JalRakshak AI database.

Populates:
  - 45 Districts (Punjab & Haryana)
  - 1,845 Weekly groundwater depth readings (45 districts x 41 weeks)
  - 24 Registered farm plots with crop & geospatial data
  - 12 Smart tubewell pump stations with telemetry & status
  - Default platform threshold & notification settings

Works seamlessly across:
  - sqlite    (default local file: jalrakshak.db)
  - mysql     (Amazon RDS MySQL)
  - dynamodb  (Amazon DynamoDB / Local)
"""
import argparse
import json
import math
import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

WEEKS = 41

DISTRICT_META = {
    "Ludhiana": {"state": "punjab", "lat": 30.9010, "lng": 75.8573, "farms": 38, "baseDepth": 35.1},
    "Amritsar": {"state": "punjab", "lat": 31.6340, "lng": 74.8723, "farms": 42, "baseDepth": 24.97},
    "Jalandhar": {"state": "punjab", "lat": 31.3256, "lng": 75.5792, "farms": 45, "baseDepth": 28.13},
    "Bathinda": {"state": "punjab", "lat": 30.2110, "lng": 74.9455, "farms": 35, "baseDepth": 18.30},
    "Patiala": {"state": "punjab", "lat": 30.3398, "lng": 76.3869, "farms": 54, "baseDepth": 41.95},
    "Barnala": {"state": "punjab", "lat": 30.3782, "lng": 75.5461, "farms": 22, "baseDepth": 32.50},
    "Fatehgarh Sahib": {"state": "punjab", "lat": 30.6522, "lng": 76.3963, "farms": 18, "baseDepth": 26.80},
    "Fazilka": {"state": "punjab", "lat": 30.4017, "lng": 74.0289, "farms": 16, "baseDepth": 31.20},
    "Firozpur": {"state": "punjab", "lat": 30.9256, "lng": 74.6142, "farms": 24, "baseDepth": 24.50},
    "Gurdaspur": {"state": "punjab", "lat": 32.0410, "lng": 75.4017, "farms": 28, "baseDepth": 18.90},
    "Hoshiarpur": {"state": "punjab", "lat": 31.5339, "lng": 75.9119, "farms": 26, "baseDepth": 16.40},
    "Kapurthala": {"state": "punjab", "lat": 31.3800, "lng": 75.3800, "farms": 20, "baseDepth": 23.80},
    "Malerkotla": {"state": "punjab", "lat": 30.5289, "lng": 75.8803, "farms": 14, "baseDepth": 27.60},
    "Mansa": {"state": "punjab", "lat": 29.9988, "lng": 75.3938, "farms": 19, "baseDepth": 25.40},
    "Moga": {"state": "punjab", "lat": 30.8155, "lng": 75.1719, "farms": 21, "baseDepth": 33.80},
    "Pathankot": {"state": "punjab", "lat": 32.2746, "lng": 75.6525, "farms": 15, "baseDepth": 14.20},
    "Rupnagar (Ropar)": {"state": "punjab", "lat": 30.9667, "lng": 76.5333, "farms": 17, "baseDepth": 17.80},
    "SAS Nagar (Mohali)": {"state": "punjab", "lat": 30.7046, "lng": 76.7179, "farms": 12, "baseDepth": 22.30},
    "Sangrur": {"state": "punjab", "lat": 30.2440, "lng": 75.8417, "farms": 27, "baseDepth": 36.20},
    "SBS Nagar (Nawanshahr)": {"state": "punjab", "lat": 31.1211, "lng": 76.1178, "farms": 13, "baseDepth": 21.50},
    "Sri Anandpur Sahib": {"state": "punjab", "lat": 31.5667, "lng": 76.5000, "farms": 11, "baseDepth": 19.20},
    "Sri Muktsar Sahib": {"state": "punjab", "lat": 30.4767, "lng": 74.5133, "farms": 18, "baseDepth": 28.90},
    "Tarn Taran": {"state": "punjab", "lat": 31.4511, "lng": 74.9711, "farms": 23, "baseDepth": 22.70},
    "Kurukshetra": {"state": "haryana", "lat": 29.9693, "lng": 76.8782, "farms": 31, "baseDepth": 35.49},
    "Kaithal": {"state": "haryana", "lat": 29.8003, "lng": 76.3994, "farms": 28, "baseDepth": 29.87},
    "Mahendragarh": {"state": "haryana", "lat": 28.2667, "lng": 76.1667, "farms": 22, "baseDepth": 48.54},
    "Bhiwani": {"state": "haryana", "lat": 28.7931, "lng": 76.1378, "farms": 26, "baseDepth": 25.02},
    "Karnal": {"state": "haryana", "lat": 29.6857, "lng": 76.9905, "farms": 67, "baseDepth": 18.13},
    "Gurugram": {"state": "haryana", "lat": 28.4595, "lng": 77.0266, "farms": 19, "baseDepth": 39.91},
    "Ambala": {"state": "haryana", "lat": 30.3782, "lng": 76.7767, "farms": 25, "baseDepth": 24.80},
    "Charkhi Dadri": {"state": "haryana", "lat": 28.5933, "lng": 76.2711, "farms": 16, "baseDepth": 26.40},
    "Faridabad": {"state": "haryana", "lat": 28.4089, "lng": 77.3178, "farms": 21, "baseDepth": 32.10},
    "Fatehabad": {"state": "haryana", "lat": 29.5178, "lng": 75.4597, "farms": 20, "baseDepth": 34.60},
    "Hisar": {"state": "haryana", "lat": 29.1492, "lng": 75.7217, "farms": 29, "baseDepth": 27.30},
    "Jhajjar": {"state": "haryana", "lat": 28.6061, "lng": 76.6506, "farms": 17, "baseDepth": 31.80},
    "Jind": {"state": "haryana", "lat": 29.3153, "lng": 76.3142, "farms": 23, "baseDepth": 26.90},
    "Nuh (Mewat)": {"state": "haryana", "lat": 28.1033, "lng": 77.0000, "farms": 14, "baseDepth": 23.50},
    "Palwal": {"state": "haryana", "lat": 28.1447, "lng": 77.3269, "farms": 18, "baseDepth": 25.70},
    "Panchkula": {"state": "haryana", "lat": 30.6942, "lng": 76.8606, "farms": 13, "baseDepth": 15.60},
    "Panipat": {"state": "haryana", "lat": 29.3909, "lng": 76.9635, "farms": 24, "baseDepth": 24.20},
    "Rewari": {"state": "haryana", "lat": 28.1989, "lng": 76.6167, "farms": 19, "baseDepth": 26.10},
    "Rohtak": {"state": "haryana", "lat": 28.8955, "lng": 76.6066, "farms": 27, "baseDepth": 22.40},
    "Sirsa": {"state": "haryana", "lat": 29.5349, "lng": 75.0289, "farms": 22, "baseDepth": 35.90},
    "Sonipat": {"state": "haryana", "lat": 28.9845, "lng": 77.0151, "farms": 26, "baseDepth": 23.90},
    "Yamunanagar": {"state": "haryana", "lat": 30.1290, "lng": 77.2674, "farms": 20, "baseDepth": 17.30},
}

INITIAL_PLOTS = [
    {"id": "KRL-01", "belt": "Karnal", "district": "Karnal", "state": "haryana", "owner": "Raman Singh", "acres": 5.2, "crop": "Paddy", "stage": "Mid-season", "lat": 29.7245, "lng": 76.9835, "seed": 11, "discharge": 18.0, "runtime": 6.0, "riskLevel": "High"},
    {"id": "KRL-02", "belt": "Karnal", "district": "Karnal", "state": "haryana", "owner": "Gurpreet Kaur", "acres": 3.4, "crop": "Wheat", "stage": "Development", "lat": 29.7180, "lng": 76.9960, "seed": 12, "discharge": 16.0, "runtime": 4.5, "riskLevel": "Normal"},
    {"id": "KRL-03", "belt": "Karnal", "district": "Karnal", "state": "haryana", "owner": "Balbir Singh", "acres": 7.8, "crop": "Paddy", "stage": "Mid-season", "lat": 29.7135, "lng": 76.9810, "seed": 13, "discharge": 20.0, "runtime": 6.5, "riskLevel": "Elevated"},
    {"id": "KRL-04", "belt": "Karnal", "district": "Karnal", "state": "haryana", "owner": "Harpreet Kaur", "acres": 2.6, "crop": "Maize", "stage": "Initial", "lat": 29.7290, "lng": 76.9975, "seed": 14, "discharge": 14.0, "runtime": 3.8, "riskLevel": "Normal"},
    {"id": "LDH-05", "belt": "Ludhiana", "district": "Ludhiana", "state": "punjab", "owner": "Manpreet Singh", "acres": 9.6, "crop": "Paddy", "stage": "Mid-season", "lat": 30.8645, "lng": 75.9435, "seed": 15, "discharge": 24.0, "runtime": 7.0, "riskLevel": "Critical"},
    {"id": "LDH-06", "belt": "Ludhiana", "district": "Ludhiana", "state": "punjab", "owner": "Jaspreet Kaur", "acres": 4.4, "crop": "Cotton", "stage": "Development", "lat": 30.8570, "lng": 75.9560, "seed": 16, "discharge": 16.0, "runtime": 5.0, "riskLevel": "Elevated"},
    {"id": "LDH-07", "belt": "Ludhiana", "district": "Ludhiana", "state": "punjab", "owner": "Kuldeep Singh", "acres": 6.2, "crop": "Paddy", "stage": "Late", "lat": 30.8525, "lng": 75.9410, "seed": 17, "discharge": 22.0, "runtime": 6.0, "riskLevel": "High"},
    {"id": "LDH-08", "belt": "Ludhiana", "district": "Ludhiana", "state": "punjab", "owner": "Simran Kaur", "acres": 3.0, "crop": "Wheat", "stage": "Initial", "lat": 30.8690, "lng": 75.9585, "seed": 18, "discharge": 15.0, "runtime": 4.0, "riskLevel": "Normal"},
    {"id": "PTL-09", "belt": "Patiala", "district": "Patiala", "state": "punjab", "owner": "Davinder Singh", "acres": 8.4, "crop": "Paddy", "stage": "Mid-season", "lat": 30.3645, "lng": 76.1335, "seed": 19, "discharge": 25.0, "runtime": 7.5, "riskLevel": "Critical"},
    {"id": "PTL-10", "belt": "Patiala", "district": "Patiala", "state": "punjab", "owner": "Amarjeet Kaur", "acres": 5.0, "crop": "Sugarcane", "stage": "Mid-season", "lat": 30.3570, "lng": 76.1460, "seed": 20, "discharge": 18.0, "runtime": 5.5, "riskLevel": "Elevated"},
    {"id": "PTL-11", "belt": "Patiala", "district": "Patiala", "state": "punjab", "owner": "Sukhdev Ram", "acres": 2.8, "crop": "Maize", "stage": "Development", "lat": 30.3525, "lng": 76.1310, "seed": 21, "discharge": 14.0, "runtime": 4.0, "riskLevel": "Normal"},
    {"id": "PTL-12", "belt": "Patiala", "district": "Patiala", "state": "punjab", "owner": "Kulwant Singh", "acres": 11.2, "crop": "Paddy", "stage": "Mid-season", "lat": 30.3690, "lng": 76.1485, "seed": 22, "discharge": 28.0, "runtime": 8.0, "riskLevel": "Critical"},
    {"id": "KUK-13", "belt": "Kurukshetra", "district": "Kurukshetra", "state": "haryana", "owner": "Rajesh Kumar", "acres": 5.0, "crop": "Paddy", "stage": "Mid-season", "lat": 29.9945, "lng": 76.8535, "seed": 23, "discharge": 20.0, "runtime": 6.0, "riskLevel": "High"},
    {"id": "KUK-14", "belt": "Kurukshetra", "district": "Kurukshetra", "state": "haryana", "owner": "Sunita Kaur", "acres": 3.6, "crop": "Wheat", "stage": "Development", "lat": 29.9870, "lng": 76.8660, "seed": 24, "discharge": 16.0, "runtime": 4.5, "riskLevel": "Normal"},
    {"id": "KUK-15", "belt": "Kurukshetra", "district": "Kurukshetra", "state": "haryana", "owner": "Mahesh Gill", "acres": 6.8, "crop": "Paddy", "stage": "Late", "lat": 29.9825, "lng": 76.8510, "seed": 25, "discharge": 22.0, "runtime": 6.2, "riskLevel": "Elevated"},
    {"id": "KUK-16", "belt": "Kurukshetra", "district": "Kurukshetra", "state": "haryana", "owner": "Pawan Singh", "acres": 4.2, "crop": "Maize", "stage": "Initial", "lat": 29.9990, "lng": 76.8685, "seed": 26, "discharge": 15.0, "runtime": 4.2, "riskLevel": "Normal"},
    {"id": "SGR-17", "belt": "Sangrur", "district": "Sangrur", "state": "punjab", "owner": "Harjinder Singh", "acres": 10.4, "crop": "Paddy", "stage": "Mid-season", "lat": 30.3045, "lng": 75.8235, "seed": 27, "discharge": 26.0, "runtime": 7.8, "riskLevel": "Critical"},
    {"id": "SGR-18", "belt": "Sangrur", "district": "Sangrur", "state": "punjab", "owner": "Manjit Kaur", "acres": 4.8, "crop": "Cotton", "stage": "Development", "lat": 30.2970, "lng": 75.8360, "seed": 28, "discharge": 17.0, "runtime": 5.0, "riskLevel": "Elevated"},
    {"id": "SGR-19", "belt": "Sangrur", "district": "Sangrur", "state": "punjab", "owner": "Gurmukh Singh", "acres": 5.6, "crop": "Paddy", "stage": "Mid-season", "lat": 30.2925, "lng": 75.8210, "seed": 29, "discharge": 20.0, "runtime": 6.0, "riskLevel": "High"},
    {"id": "SGR-20", "belt": "Sangrur", "district": "Sangrur", "state": "punjab", "owner": "Balwinder Kaur", "acres": 2.5, "crop": "Wheat", "stage": "Initial", "lat": 30.3090, "lng": 75.8385, "seed": 30, "discharge": 14.0, "runtime": 3.8, "riskLevel": "Normal"},
    {"id": "MGA-21", "belt": "Moga", "district": "Moga", "state": "punjab", "owner": "Joginder Singh", "acres": 7.2, "crop": "Paddy", "stage": "Mid-season", "lat": 30.7545, "lng": 75.2435, "seed": 31, "discharge": 22.0, "runtime": 6.5, "riskLevel": "High"},
    {"id": "MGA-22", "belt": "Moga", "district": "Moga", "state": "punjab", "owner": "Harbhajan Kaur", "acres": 3.8, "crop": "Maize", "stage": "Development", "lat": 30.7470, "lng": 75.2560, "seed": 32, "discharge": 15.0, "runtime": 4.2, "riskLevel": "Normal"},
    {"id": "MGA-23", "belt": "Moga", "district": "Moga", "state": "punjab", "owner": "Nirmal Singh", "acres": 6.4, "crop": "Cotton", "stage": "Mid-season", "lat": 30.7425, "lng": 75.2410, "seed": 33, "discharge": 18.0, "runtime": 5.4, "riskLevel": "Elevated"},
    {"id": "MGA-24", "belt": "Moga", "district": "Moga", "state": "punjab", "owner": "Surjit Kaur", "acres": 9.0, "crop": "Paddy", "stage": "Late", "lat": 30.7590, "lng": 75.2585, "seed": 34, "discharge": 24.0, "runtime": 7.0, "riskLevel": "Critical"},
]

INITIAL_TUBEWELLS = [
    {"id": "TW-KRL-01", "plotId": "KRL-01", "farmerName": "Raman Singh", "district": "Karnal", "state": "haryana", "lat": 29.7245, "lng": 76.9835, "depth": 18.5, "dischargeLps": 5.0, "status": "RUNNING", "runningHours": 5.2, "powerKw": 5.5, "dailyExtractionKl": 93.6, "feederWindow": "morning"},
    {"id": "TW-KRL-02", "plotId": "KRL-03", "farmerName": "Balbir Singh", "district": "Karnal", "state": "haryana", "lat": 29.7135, "lng": 76.9810, "depth": 19.2, "dischargeLps": 5.5, "status": "IDLE", "runningHours": 4.0, "powerKw": 5.0, "dailyExtractionKl": 79.2, "feederWindow": "morning"},
    {"id": "TW-LDH-01", "plotId": "LDH-05", "farmerName": "Manpreet Singh", "district": "Ludhiana", "state": "punjab", "lat": 30.8645, "lng": 75.9435, "depth": 35.8, "dischargeLps": 6.5, "status": "RUNNING", "runningHours": 6.8, "powerKw": 7.5, "dailyExtractionKl": 159.1, "feederWindow": "night"},
    {"id": "TW-LDH-02", "plotId": "LDH-07", "farmerName": "Kuldeep Singh", "district": "Ludhiana", "state": "punjab", "lat": 30.8525, "lng": 75.9410, "depth": 36.4, "dischargeLps": 6.0, "status": "IDLE", "runningHours": 4.5, "powerKw": 6.0, "dailyExtractionKl": 97.2, "feederWindow": "morning"},
    {"id": "TW-PTL-01", "plotId": "PTL-09", "farmerName": "Davinder Singh", "district": "Patiala", "state": "punjab", "lat": 30.3645, "lng": 76.1335, "depth": 42.1, "dischargeLps": 7.0, "status": "RUNNING", "runningHours": 7.2, "powerKw": 8.0, "dailyExtractionKl": 181.4, "feederWindow": "night"},
    {"id": "TW-PTL-02", "plotId": "PTL-12", "farmerName": "Kulwant Singh", "district": "Patiala", "state": "punjab", "lat": 30.3690, "lng": 76.1485, "depth": 43.5, "dischargeLps": 7.5, "status": "RUNNING", "runningHours": 7.5, "powerKw": 9.0, "dailyExtractionKl": 202.5, "feederWindow": "night"},
    {"id": "TW-KUK-01", "plotId": "KUK-13", "farmerName": "Rajesh Kumar", "district": "Kurukshetra", "state": "haryana", "lat": 29.9945, "lng": 76.8535, "depth": 36.0, "dischargeLps": 5.5, "status": "IDLE", "runningHours": 4.8, "powerKw": 5.5, "dailyExtractionKl": 95.0, "feederWindow": "morning"},
    {"id": "TW-KUK-02", "plotId": "KUK-15", "farmerName": "Mahesh Gill", "district": "Kurukshetra", "state": "haryana", "lat": 29.9825, "lng": 76.8510, "depth": 37.2, "dischargeLps": 6.0, "status": "RUNNING", "runningHours": 5.5, "powerKw": 6.5, "dailyExtractionKl": 118.8, "feederWindow": "morning"},
    {"id": "TW-SGR-01", "plotId": "SGR-17", "farmerName": "Harjinder Singh", "district": "Sangrur", "state": "punjab", "lat": 30.3045, "lng": 75.8235, "depth": 38.0, "dischargeLps": 7.0, "status": "RUNNING", "runningHours": 7.0, "powerKw": 8.5, "dailyExtractionKl": 176.4, "feederWindow": "night"},
    {"id": "TW-SGR-02", "plotId": "SGR-19", "farmerName": "Gurmukh Singh", "district": "Sangrur", "state": "punjab", "lat": 30.2925, "lng": 75.8210, "depth": 37.5, "dischargeLps": 5.8, "status": "IDLE", "runningHours": 4.2, "powerKw": 6.0, "dailyExtractionKl": 87.7, "feederWindow": "morning"},
    {"id": "TW-MGA-01", "plotId": "MGA-21", "farmerName": "Joginder Singh", "district": "Moga", "state": "punjab", "lat": 30.7545, "lng": 75.2435, "depth": 34.2, "dischargeLps": 6.2, "status": "RUNNING", "runningHours": 6.0, "powerKw": 7.0, "dailyExtractionKl": 133.9, "feederWindow": "morning"},
    {"id": "TW-MGA-02", "plotId": "MGA-24", "farmerName": "Surjit Kaur", "district": "Moga", "state": "punjab", "lat": 30.7590, "lng": 75.2585, "depth": 35.1, "dischargeLps": 6.8, "status": "IDLE", "runningHours": 4.6, "powerKw": 7.5, "dailyExtractionKl": 112.6, "feederWindow": "night"}
]

DEFAULT_SETTINGS = {
    "threshold_normal": 80,
    "threshold_watch": 100,
    "threshold_high": 120,
    "threshold_critical": 150,
    "alert_email": True,
    "alert_sms": True,
    "alert_weekly_reports": True,
    "language": "English"
}


def week_date_str(w: int) -> str:
    return (datetime(2026, 1, 4) + timedelta(days=(w - 1) * 7)).strftime("%Y-%m-%d")


def generate_weekly(district: str):
    meta = DISTRICT_META[district]
    rows = []
    for w in range(1, WEEKS + 1):
        seasonal_factor = 0.0
        if 14 <= w <= 22:
            seasonal_factor = (w - 14) * 0.35
        elif 23 <= w <= 35:
            seasonal_factor = 8 * 0.35 - (w - 23) * 0.15
        elif w > 35:
            seasonal_factor = max(0, 8 * 0.35 - 12 * 0.15 - (w - 35) * 0.2)
        noise = math.sin(w * 1.7 + meta["baseDepth"]) * 0.4 + math.cos(w * 0.9) * 0.3
        depth = round(meta["baseDepth"] + seasonal_factor + noise, 2)
        rows.append({"week": w, "date": week_date_str(w), "depth": depth})
    return rows


def seed_all(be=None):
    if be is None:
        from db import get_backend
        be = get_backend()

    print(f"Seeding database backend: {getattr(be, 'name', 'unknown')} ...")
    be.init_schema()

    # 1. Districts
    for d, m in DISTRICT_META.items():
        be.upsert_district({"district": d, **m})
    print(f"  [OK] {len(DISTRICT_META)} districts seeded")

    # 2. Groundwater weekly time series
    total_readings = 0
    for d in DISTRICT_META:
        for row in generate_weekly(d):
            be.put_reading(d, row["week"], row["date"], row["depth"])
            total_readings += 1
    print(f"  [OK] {total_readings} weekly groundwater readings seeded")

    # 3. Farm Plots
    for p in INITIAL_PLOTS:
        be.upsert_plot(p)
    print(f"  [OK] {len(INITIAL_PLOTS)} agricultural farm plots seeded")

    # 4. Smart Tubewells
    for tw in INITIAL_TUBEWELLS:
        be.upsert_tubewell(tw)
    print(f"  [OK] {len(INITIAL_TUBEWELLS)} smart tubewell stations seeded")

    # 5. Default Settings
    be.save_settings(DEFAULT_SETTINGS)
    print("  [OK] Platform threshold & alert settings initialized")

    print("\nDatabase is fully seeded and verified:")
    print(f"  - Districts: {be.count_districts()}")
    print(f"  - Readings:  {be.count_readings()}")
    print(f"  - Plots:     {be.count_plots()}")
    print(f"  - Tubewells: {be.count_tubewells()}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Seed JalRakshak AI database")
    parser.add_argument("--local", action="store_true", help="Force DynamoDB Local")
    parser.add_argument("--sqlite", action="store_true", help="Force SQLite local database")
    args = parser.parse_args()

    if args.local:
        os.environ["DYNAMODB_ENDPOINT_URL"] = "http://localhost:8000"
        os.environ["DB_BACKEND"] = "dynamodb"
    elif args.sqlite:
        os.environ["DB_BACKEND"] = "sqlite"

    from db import get_backend
    seed_all(get_backend())


if __name__ == "__main__":
    main()
