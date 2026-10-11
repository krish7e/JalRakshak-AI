"""
Seed script for JalRakshak AI — DynamoDB groundwater tables.

Generates EXACTLY the same deterministic dataset that index.html's
GroundwaterDataService / GroundwaterMonitoringService produce in-browser,
so switching the dashboard between local-generated data and DynamoDB
returns identical numbers.

Tables created (names come from .env):
  - <PREFIX>-groundwater-weekly   PK: district#week            (45 districts x 41 weeks = 1845 items)
  - <PREFIX>-district-meta        PK: district                 (45 items)
  - <PREFIX>-climate-weekly       PK: district#week            (same shape as weekly)

Usage:
  python seed_data.py --local     # DynamoDB Local on localhost:8000
  python seed_data.py             # real AWS (uses ~/.aws credentials or env vars)
"""
import argparse
import json
import math
import os
from datetime import datetime, timedelta

from decimal import Decimal
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

TABLE_PREFIX = os.getenv("DYNAMODB_TABLE_PREFIX", "jalrakshak")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL") or None

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


def week_date_str(w: int) -> str:
    """Mirror of JS: new Date(2026, 0, 4 + (w-1)*7).toISOString().split('T')[0]
    Note: JS uses *local* time; we store the calendar date directly."""
    return (datetime(2026, 1, 4) + timedelta(days=(w - 1) * 7)).strftime("%Y-%m-%d")


def generate_weekly(district: str):
    """Exact port of GroundwaterDataService._generateWeeklyData (index.html lines ~1354-1372)."""
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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true",
                        help="Seed DynamoDB Local (localhost:8000) instead of the .env backend")
    args = parser.parse_args(argv)

    if args.local:
        os.environ["DYNAMODB_ENDPOINT_URL"] = "http://localhost:8000"
        os.environ["DB_BACKEND"] = "dynamodb"

    from db import get_backend, BACKEND
    be = get_backend()
    print(f"Seeding backend: {BACKEND} ...")
    be.init_schema()

    for d, m in DISTRICT_META.items():
        be.upsert_district({"district": d, **m})
    print(f"  wrote {len(DISTRICT_META)} districts")

    total = 0
    for d in DISTRICT_META:
        for row in generate_weekly(d):
            be.put_reading(d, row["week"], row["date"], row["depth"])
            total += 1
    print(f"  wrote {total} weekly groundwater readings")
    print(f"  verify: {be.count_districts()} districts, {be.count_readings()} readings")
    print("Done.")


if __name__ == "__main__":
    main()
