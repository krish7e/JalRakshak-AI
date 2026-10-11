"""
Fast Bulk-Insert Seeder for JalRakshak AI - MySQL RDS edition.
Uses executemany() for batch inserts.
"""
import math
import os
from datetime import datetime, timedelta

import pymysql
import pymysql.cursors

HOST     = os.getenv("RDS_HOST",     "jalrakshak.claygkmqe1sb.ap-southeast-2.rds.amazonaws.com")
PORT     = int(os.getenv("RDS_PORT", "3306"))
USER     = os.getenv("RDS_USER",     "admin")
PASSWORD = os.getenv("RDS_PASSWORD", "karan9873026649")
DATABASE = os.getenv("RDS_DATABASE", "jalrakshak")
WEEKS    = 41

DISTRICT_META = {
    "Ludhiana":               {"state":"punjab",  "lat":30.9010,"lng":75.8573,"farms":38,"baseDepth":35.1},
    "Amritsar":               {"state":"punjab",  "lat":31.6340,"lng":74.8723,"farms":42,"baseDepth":24.97},
    "Jalandhar":              {"state":"punjab",  "lat":31.3256,"lng":75.5792,"farms":45,"baseDepth":28.13},
    "Bathinda":               {"state":"punjab",  "lat":30.2110,"lng":74.9455,"farms":35,"baseDepth":18.30},
    "Patiala":                {"state":"punjab",  "lat":30.3398,"lng":76.3869,"farms":54,"baseDepth":41.95},
    "Barnala":                {"state":"punjab",  "lat":30.3782,"lng":75.5461,"farms":22,"baseDepth":32.50},
    "Fatehgarh Sahib":        {"state":"punjab",  "lat":30.6522,"lng":76.3963,"farms":18,"baseDepth":26.80},
    "Fazilka":                {"state":"punjab",  "lat":30.4017,"lng":74.0289,"farms":16,"baseDepth":31.20},
    "Firozpur":               {"state":"punjab",  "lat":30.9256,"lng":74.6142,"farms":24,"baseDepth":24.50},
    "Gurdaspur":              {"state":"punjab",  "lat":32.0410,"lng":75.4017,"farms":28,"baseDepth":18.90},
    "Hoshiarpur":             {"state":"punjab",  "lat":31.5339,"lng":75.9119,"farms":26,"baseDepth":16.40},
    "Kapurthala":             {"state":"punjab",  "lat":31.3800,"lng":75.3800,"farms":20,"baseDepth":23.80},
    "Malerkotla":             {"state":"punjab",  "lat":30.5289,"lng":75.8803,"farms":14,"baseDepth":27.60},
    "Mansa":                  {"state":"punjab",  "lat":29.9988,"lng":75.3938,"farms":19,"baseDepth":25.40},
    "Moga":                   {"state":"punjab",  "lat":30.8155,"lng":75.1719,"farms":21,"baseDepth":33.80},
    "Pathankot":              {"state":"punjab",  "lat":32.2746,"lng":75.6525,"farms":15,"baseDepth":14.20},
    "Rupnagar (Ropar)":       {"state":"punjab",  "lat":30.9667,"lng":76.5333,"farms":17,"baseDepth":17.80},
    "SAS Nagar (Mohali)":     {"state":"punjab",  "lat":30.7046,"lng":76.7179,"farms":12,"baseDepth":22.30},
    "Sangrur":                {"state":"punjab",  "lat":30.2440,"lng":75.8417,"farms":27,"baseDepth":36.20},
    "SBS Nagar (Nawanshahr)": {"state":"punjab",  "lat":31.1211,"lng":76.1178,"farms":13,"baseDepth":21.50},
    "Sri Anandpur Sahib":     {"state":"punjab",  "lat":31.5667,"lng":76.5000,"farms":11,"baseDepth":19.20},
    "Sri Muktsar Sahib":      {"state":"punjab",  "lat":30.4767,"lng":74.5133,"farms":18,"baseDepth":28.90},
    "Tarn Taran":             {"state":"punjab",  "lat":31.4511,"lng":74.9711,"farms":23,"baseDepth":22.70},
    "Kurukshetra":            {"state":"haryana", "lat":29.9693,"lng":76.8782,"farms":31,"baseDepth":35.49},
    "Kaithal":                {"state":"haryana", "lat":29.8003,"lng":76.3994,"farms":28,"baseDepth":29.87},
    "Mahendragarh":           {"state":"haryana", "lat":28.2667,"lng":76.1667,"farms":22,"baseDepth":48.54},
    "Bhiwani":                {"state":"haryana", "lat":28.7931,"lng":76.1378,"farms":26,"baseDepth":25.02},
    "Karnal":                 {"state":"haryana", "lat":29.6857,"lng":76.9905,"farms":67,"baseDepth":18.13},
    "Gurugram":               {"state":"haryana", "lat":28.4595,"lng":77.0266,"farms":19,"baseDepth":39.91},
    "Ambala":                 {"state":"haryana", "lat":30.3782,"lng":76.7767,"farms":25,"baseDepth":24.80},
    "Charkhi Dadri":          {"state":"haryana", "lat":28.5933,"lng":76.2711,"farms":16,"baseDepth":26.40},
    "Faridabad":              {"state":"haryana", "lat":28.4089,"lng":77.3178,"farms":21,"baseDepth":32.10},
    "Fatehabad":              {"state":"haryana", "lat":29.5178,"lng":75.4597,"farms":20,"baseDepth":34.60},
    "Hisar":                  {"state":"haryana", "lat":29.1492,"lng":75.7217,"farms":29,"baseDepth":27.30},
    "Jhajjar":                {"state":"haryana", "lat":28.6061,"lng":76.6506,"farms":17,"baseDepth":31.80},
    "Jind":                   {"state":"haryana", "lat":29.3153,"lng":76.3142,"farms":23,"baseDepth":26.90},
    "Nuh (Mewat)":            {"state":"haryana", "lat":28.1033,"lng":77.0000,"farms":14,"baseDepth":23.50},
    "Palwal":                 {"state":"haryana", "lat":28.1447,"lng":77.3269,"farms":18,"baseDepth":25.70},
    "Panchkula":              {"state":"haryana", "lat":30.6942,"lng":76.8606,"farms":13,"baseDepth":15.60},
    "Panipat":                {"state":"haryana", "lat":29.3909,"lng":76.9635,"farms":24,"baseDepth":24.20},
    "Rewari":                 {"state":"haryana", "lat":28.1989,"lng":76.6167,"farms":19,"baseDepth":26.10},
    "Rohtak":                 {"state":"haryana", "lat":28.8955,"lng":76.6066,"farms":27,"baseDepth":22.40},
    "Sirsa":                  {"state":"haryana", "lat":29.5349,"lng":75.0289,"farms":22,"baseDepth":35.90},
    "Sonipat":                {"state":"haryana", "lat":28.9845,"lng":77.0151,"farms":26,"baseDepth":23.90},
    "Yamunanagar":            {"state":"haryana", "lat":30.1290,"lng":77.2674,"farms":20,"baseDepth":17.30},
}

INITIAL_PLOTS = [
    {"id":"KRL-01","belt":"Karnal","district":"Karnal","state":"haryana","owner":"Raman Singh","acres":5.2,"crop":"Paddy","stage":"Mid-season","lat":29.7245,"lng":76.9835,"seed":11,"discharge":18.0,"runtime":6.0,"riskLevel":"High"},
    {"id":"KRL-02","belt":"Karnal","district":"Karnal","state":"haryana","owner":"Gurpreet Kaur","acres":3.4,"crop":"Wheat","stage":"Development","lat":29.7180,"lng":76.9960,"seed":12,"discharge":16.0,"runtime":4.5,"riskLevel":"Normal"},
    {"id":"KRL-03","belt":"Karnal","district":"Karnal","state":"haryana","owner":"Balbir Singh","acres":7.8,"crop":"Paddy","stage":"Mid-season","lat":29.7135,"lng":76.9810,"seed":13,"discharge":20.0,"runtime":6.5,"riskLevel":"Elevated"},
    {"id":"KRL-04","belt":"Karnal","district":"Karnal","state":"haryana","owner":"Harpreet Kaur","acres":2.6,"crop":"Maize","stage":"Initial","lat":29.7290,"lng":76.9975,"seed":14,"discharge":14.0,"runtime":3.8,"riskLevel":"Normal"},
    {"id":"LDH-05","belt":"Ludhiana","district":"Ludhiana","state":"punjab","owner":"Manpreet Singh","acres":9.6,"crop":"Paddy","stage":"Mid-season","lat":30.8645,"lng":75.9435,"seed":15,"discharge":24.0,"runtime":7.0,"riskLevel":"Critical"},
    {"id":"LDH-06","belt":"Ludhiana","district":"Ludhiana","state":"punjab","owner":"Jaspreet Kaur","acres":4.4,"crop":"Cotton","stage":"Development","lat":30.8570,"lng":75.9560,"seed":16,"discharge":16.0,"runtime":5.0,"riskLevel":"Elevated"},
    {"id":"LDH-07","belt":"Ludhiana","district":"Ludhiana","state":"punjab","owner":"Kuldeep Singh","acres":6.2,"crop":"Paddy","stage":"Late","lat":30.8525,"lng":75.9410,"seed":17,"discharge":22.0,"runtime":6.0,"riskLevel":"High"},
    {"id":"LDH-08","belt":"Ludhiana","district":"Ludhiana","state":"punjab","owner":"Simran Kaur","acres":3.0,"crop":"Wheat","stage":"Initial","lat":30.8690,"lng":75.9585,"seed":18,"discharge":15.0,"runtime":4.0,"riskLevel":"Normal"},
    {"id":"PTL-09","belt":"Patiala","district":"Patiala","state":"punjab","owner":"Davinder Singh","acres":8.4,"crop":"Paddy","stage":"Mid-season","lat":30.3645,"lng":76.1335,"seed":19,"discharge":25.0,"runtime":7.5,"riskLevel":"Critical"},
    {"id":"PTL-10","belt":"Patiala","district":"Patiala","state":"punjab","owner":"Amarjeet Kaur","acres":5.0,"crop":"Sugarcane","stage":"Mid-season","lat":30.3570,"lng":76.1460,"seed":20,"discharge":18.0,"runtime":5.5,"riskLevel":"Elevated"},
    {"id":"PTL-11","belt":"Patiala","district":"Patiala","state":"punjab","owner":"Sukhdev Ram","acres":2.8,"crop":"Maize","stage":"Development","lat":30.3525,"lng":76.1310,"seed":21,"discharge":14.0,"runtime":4.0,"riskLevel":"Normal"},
    {"id":"PTL-12","belt":"Patiala","district":"Patiala","state":"punjab","owner":"Kulwant Singh","acres":11.2,"crop":"Paddy","stage":"Mid-season","lat":30.3690,"lng":76.1485,"seed":22,"discharge":28.0,"runtime":8.0,"riskLevel":"Critical"},
    {"id":"KUK-13","belt":"Kurukshetra","district":"Kurukshetra","state":"haryana","owner":"Rajesh Kumar","acres":5.0,"crop":"Paddy","stage":"Mid-season","lat":29.9945,"lng":76.8535,"seed":23,"discharge":20.0,"runtime":6.0,"riskLevel":"High"},
    {"id":"KUK-14","belt":"Kurukshetra","district":"Kurukshetra","state":"haryana","owner":"Sunita Kaur","acres":3.6,"crop":"Wheat","stage":"Development","lat":29.9870,"lng":76.8660,"seed":24,"discharge":16.0,"runtime":4.5,"riskLevel":"Normal"},
    {"id":"KUK-15","belt":"Kurukshetra","district":"Kurukshetra","state":"haryana","owner":"Mahesh Gill","acres":6.8,"crop":"Paddy","stage":"Late","lat":29.9825,"lng":76.8510,"seed":25,"discharge":22.0,"runtime":6.2,"riskLevel":"Elevated"},
    {"id":"KUK-16","belt":"Kurukshetra","district":"Kurukshetra","state":"haryana","owner":"Pawan Singh","acres":4.2,"crop":"Maize","stage":"Initial","lat":29.9990,"lng":76.8685,"seed":26,"discharge":15.0,"runtime":4.2,"riskLevel":"Normal"},
    {"id":"SGR-17","belt":"Sangrur","district":"Sangrur","state":"punjab","owner":"Harjinder Singh","acres":10.4,"crop":"Paddy","stage":"Mid-season","lat":30.3045,"lng":75.8235,"seed":27,"discharge":26.0,"runtime":7.8,"riskLevel":"Critical"},
    {"id":"SGR-18","belt":"Sangrur","district":"Sangrur","state":"punjab","owner":"Manjit Kaur","acres":4.8,"crop":"Cotton","stage":"Development","lat":30.2970,"lng":75.8360,"seed":28,"discharge":17.0,"runtime":5.0,"riskLevel":"Elevated"},
    {"id":"SGR-19","belt":"Sangrur","district":"Sangrur","state":"punjab","owner":"Gurmukh Singh","acres":5.6,"crop":"Paddy","stage":"Mid-season","lat":30.2925,"lng":75.8210,"seed":29,"discharge":20.0,"runtime":6.0,"riskLevel":"High"},
    {"id":"SGR-20","belt":"Sangrur","district":"Sangrur","state":"punjab","owner":"Balwinder Kaur","acres":2.5,"crop":"Wheat","stage":"Initial","lat":30.3090,"lng":75.8385,"seed":30,"discharge":14.0,"runtime":3.8,"riskLevel":"Normal"},
    {"id":"MGA-21","belt":"Moga","district":"Moga","state":"punjab","owner":"Joginder Singh","acres":7.2,"crop":"Paddy","stage":"Mid-season","lat":30.7545,"lng":75.2435,"seed":31,"discharge":22.0,"runtime":6.5,"riskLevel":"High"},
    {"id":"MGA-22","belt":"Moga","district":"Moga","state":"punjab","owner":"Harbhajan Kaur","acres":3.8,"crop":"Maize","stage":"Development","lat":30.7470,"lng":75.2560,"seed":32,"discharge":15.0,"runtime":4.2,"riskLevel":"Normal"},
    {"id":"MGA-23","belt":"Moga","district":"Moga","state":"punjab","owner":"Nirmal Singh","acres":6.4,"crop":"Cotton","stage":"Mid-season","lat":30.7425,"lng":75.2410,"seed":33,"discharge":18.0,"runtime":5.4,"riskLevel":"Elevated"},
    {"id":"MGA-24","belt":"Moga","district":"Moga","state":"punjab","owner":"Surjit Kaur","acres":9.0,"crop":"Paddy","stage":"Late","lat":30.7590,"lng":75.2585,"seed":34,"discharge":24.0,"runtime":7.0,"riskLevel":"Critical"},
]

INITIAL_TUBEWELLS = [
    {"id":"TW-KRL-01","plotId":"KRL-01","farmerName":"Raman Singh","district":"Karnal","state":"haryana","lat":29.7245,"lng":76.9835,"depth":18.5,"dischargeLps":5.0,"status":"RUNNING","runningHours":5.2,"powerKw":5.5,"dailyExtractionKl":93.6,"feederWindow":"morning"},
    {"id":"TW-KRL-02","plotId":"KRL-03","farmerName":"Balbir Singh","district":"Karnal","state":"haryana","lat":29.7135,"lng":76.9810,"depth":19.2,"dischargeLps":5.5,"status":"IDLE","runningHours":4.0,"powerKw":5.0,"dailyExtractionKl":79.2,"feederWindow":"morning"},
    {"id":"TW-LDH-01","plotId":"LDH-05","farmerName":"Manpreet Singh","district":"Ludhiana","state":"punjab","lat":30.8645,"lng":75.9435,"depth":35.8,"dischargeLps":6.5,"status":"RUNNING","runningHours":6.8,"powerKw":7.5,"dailyExtractionKl":159.1,"feederWindow":"night"},
    {"id":"TW-LDH-02","plotId":"LDH-07","farmerName":"Kuldeep Singh","district":"Ludhiana","state":"punjab","lat":30.8525,"lng":75.9410,"depth":36.4,"dischargeLps":6.0,"status":"IDLE","runningHours":4.5,"powerKw":6.0,"dailyExtractionKl":97.2,"feederWindow":"morning"},
    {"id":"TW-PTL-01","plotId":"PTL-09","farmerName":"Davinder Singh","district":"Patiala","state":"punjab","lat":30.3645,"lng":76.1335,"depth":42.1,"dischargeLps":7.0,"status":"RUNNING","runningHours":7.2,"powerKw":8.0,"dailyExtractionKl":181.4,"feederWindow":"night"},
    {"id":"TW-PTL-02","plotId":"PTL-12","farmerName":"Kulwant Singh","district":"Patiala","state":"punjab","lat":30.3690,"lng":76.1485,"depth":43.5,"dischargeLps":7.5,"status":"RUNNING","runningHours":7.5,"powerKw":9.0,"dailyExtractionKl":202.5,"feederWindow":"night"},
    {"id":"TW-KUK-01","plotId":"KUK-13","farmerName":"Rajesh Kumar","district":"Kurukshetra","state":"haryana","lat":29.9945,"lng":76.8535,"depth":36.0,"dischargeLps":5.5,"status":"IDLE","runningHours":4.8,"powerKw":5.5,"dailyExtractionKl":95.0,"feederWindow":"morning"},
    {"id":"TW-KUK-02","plotId":"KUK-15","farmerName":"Mahesh Gill","district":"Kurukshetra","state":"haryana","lat":29.9825,"lng":76.8510,"depth":37.2,"dischargeLps":6.0,"status":"RUNNING","runningHours":5.5,"powerKw":6.5,"dailyExtractionKl":118.8,"feederWindow":"morning"},
    {"id":"TW-SGR-01","plotId":"SGR-17","farmerName":"Harjinder Singh","district":"Sangrur","state":"punjab","lat":30.3045,"lng":75.8235,"depth":38.0,"dischargeLps":7.0,"status":"RUNNING","runningHours":7.0,"powerKw":8.5,"dailyExtractionKl":176.4,"feederWindow":"night"},
    {"id":"TW-SGR-02","plotId":"SGR-19","farmerName":"Gurmukh Singh","district":"Sangrur","state":"punjab","lat":30.2925,"lng":75.8210,"depth":37.5,"dischargeLps":5.8,"status":"IDLE","runningHours":4.2,"powerKw":6.0,"dailyExtractionKl":87.7,"feederWindow":"morning"},
    {"id":"TW-MGA-01","plotId":"MGA-21","farmerName":"Joginder Singh","district":"Moga","state":"punjab","lat":30.7545,"lng":75.2435,"depth":34.2,"dischargeLps":6.2,"status":"RUNNING","runningHours":6.0,"powerKw":7.0,"dailyExtractionKl":133.9,"feederWindow":"morning"},
    {"id":"TW-MGA-02","plotId":"MGA-24","farmerName":"Surjit Kaur","district":"Moga","state":"punjab","lat":30.7590,"lng":75.2585,"depth":35.1,"dischargeLps":6.8,"status":"IDLE","runningHours":4.6,"powerKw":7.5,"dailyExtractionKl":112.6,"feederWindow":"night"},
]

DEFAULT_SETTINGS = {
    "threshold_normal": "80", "threshold_watch": "100",
    "threshold_high": "120", "threshold_critical": "150",
    "alert_email": "true", "alert_sms": "true",
    "alert_weekly_reports": "true", "language": "English",
}


def week_date(w):
    return (datetime(2026, 1, 4) + timedelta(days=(w - 1) * 7)).strftime("%Y-%m-%d")


def generate_readings():
    rows = []
    for district, m in DISTRICT_META.items():
        bd = m["baseDepth"]
        for w in range(1, WEEKS + 1):
            sf = 0.0
            if 14 <= w <= 22:   sf = (w - 14) * 0.35
            elif 23 <= w <= 35: sf = 8 * 0.35 - (w - 23) * 0.15
            elif w > 35:        sf = max(0, 8 * 0.35 - 12 * 0.15 - (w - 35) * 0.2)
            noise = math.sin(w * 1.7 + bd) * 0.4 + math.cos(w * 0.9) * 0.3
            rows.append((district, w, week_date(w), round(bd + sf + noise, 2)))
    return rows


def main():
    print("=" * 60)
    print("JalRakshak AI - MySQL Bulk Seeder")
    print(f"Connecting to: {HOST}/{DATABASE}")
    print("=" * 60)

    conn = pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD,
        database=DATABASE, charset="utf8mb4", autocommit=False,
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=15
    )
    cur = conn.cursor()

    print("\n[1/6] Creating tables...")
    cur.execute("""CREATE TABLE IF NOT EXISTS districts (
        district VARCHAR(120) PRIMARY KEY, state VARCHAR(60) NOT NULL,
        lat DECIMAL(9,6) NOT NULL, lng DECIMAL(9,6) NOT NULL,
        farms INT NOT NULL, base_depth DECIMAL(8,2) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS groundwater_weekly (
        district VARCHAR(120) NOT NULL, week INT NOT NULL,
        reading_date DATE NULL, depth_bgl DECIMAL(8,2) NOT NULL,
        PRIMARY KEY (district, week)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS plots (
        id VARCHAR(50) PRIMARY KEY, belt VARCHAR(100) NOT NULL,
        district VARCHAR(120) NOT NULL, state VARCHAR(60) NOT NULL,
        owner VARCHAR(120) NOT NULL, acres DECIMAL(6,2) NOT NULL,
        crop VARCHAR(60) NOT NULL, stage VARCHAR(60) NOT NULL,
        lat DECIMAL(9,6) NOT NULL, lng DECIMAL(9,6) NOT NULL,
        seed INT NOT NULL DEFAULT 10, discharge DECIMAL(6,2) NOT NULL DEFAULT 18.0,
        runtime DECIMAL(6,2) NOT NULL DEFAULT 6.0, risk_level VARCHAR(40) DEFAULT 'Normal'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS tubewells (
        id VARCHAR(50) PRIMARY KEY, plot_id VARCHAR(50),
        farmer_name VARCHAR(120) NOT NULL, district VARCHAR(120) NOT NULL,
        state VARCHAR(60) NOT NULL DEFAULT 'punjab',
        lat DECIMAL(9,6) NOT NULL, lng DECIMAL(9,6) NOT NULL,
        depth DECIMAL(8,2) NOT NULL, discharge_lps DECIMAL(6,2) NOT NULL,
        status VARCHAR(30) NOT NULL DEFAULT 'IDLE',
        running_hours DECIMAL(6,2) NOT NULL DEFAULT 4.5,
        power_kw DECIMAL(6,2) NOT NULL DEFAULT 5.0,
        daily_extraction_kl DECIMAL(8,2) NOT NULL DEFAULT 81.0,
        feeder_window VARCHAR(40) DEFAULT 'morning',
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS settings (
        `key` VARCHAR(100) PRIMARY KEY, `value` TEXT NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    conn.commit()
    print("  [OK] Tables ready")

    print(f"\n[2/6] Seeding {len(DISTRICT_META)} districts...")
    cur.executemany(
        """INSERT INTO districts (district,state,lat,lng,farms,base_depth) VALUES (%s,%s,%s,%s,%s,%s)
           ON DUPLICATE KEY UPDATE state=VALUES(state),lat=VALUES(lat),lng=VALUES(lng),
           farms=VALUES(farms),base_depth=VALUES(base_depth)""",
        [(d,m["state"],m["lat"],m["lng"],m["farms"],m["baseDepth"]) for d,m in DISTRICT_META.items()]
    )
    conn.commit()
    print(f"  [OK]")

    readings = generate_readings()
    print(f"\n[3/6] Bulk-inserting {len(readings)} groundwater readings...")
    cur.executemany(
        """INSERT INTO groundwater_weekly (district,week,reading_date,depth_bgl) VALUES (%s,%s,%s,%s)
           ON DUPLICATE KEY UPDATE reading_date=VALUES(reading_date),depth_bgl=VALUES(depth_bgl)""",
        readings
    )
    conn.commit()
    print(f"  [OK]")

    print(f"\n[4/6] Seeding {len(INITIAL_PLOTS)} farm plots...")
    cur.executemany(
        """INSERT INTO plots (id,belt,district,state,owner,acres,crop,stage,lat,lng,seed,discharge,runtime,risk_level)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON DUPLICATE KEY UPDATE owner=VALUES(owner),acres=VALUES(acres),crop=VALUES(crop),
           stage=VALUES(stage),risk_level=VALUES(risk_level)""",
        [(p["id"],p["belt"],p["district"],p["state"],p["owner"],p["acres"],p["crop"],p["stage"],
          p["lat"],p["lng"],p["seed"],p["discharge"],p["runtime"],p["riskLevel"]) for p in INITIAL_PLOTS]
    )
    conn.commit()
    print(f"  [OK]")

    print(f"\n[5/6] Seeding {len(INITIAL_TUBEWELLS)} tubewells...")
    cur.executemany(
        """INSERT INTO tubewells (id,plot_id,farmer_name,district,state,lat,lng,depth,
           discharge_lps,status,running_hours,power_kw,daily_extraction_kl,feeder_window)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON DUPLICATE KEY UPDATE status=VALUES(status),depth=VALUES(depth)""",
        [(tw["id"],tw["plotId"],tw["farmerName"],tw["district"],tw["state"],
          tw["lat"],tw["lng"],tw["depth"],tw["dischargeLps"],tw["status"],
          tw["runningHours"],tw["powerKw"],tw["dailyExtractionKl"],tw["feederWindow"])
         for tw in INITIAL_TUBEWELLS]
    )
    conn.commit()
    print(f"  [OK]")

    print("\n[6/6] Seeding settings...")
    cur.executemany(
        "INSERT INTO settings (`key`,`value`) VALUES (%s,%s) ON DUPLICATE KEY UPDATE `value`=VALUES(`value`)",
        list(DEFAULT_SETTINGS.items())
    )
    conn.commit()
    print(f"  [OK]")

    cur.execute("SELECT COUNT(*) AS n FROM districts");          nd = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM groundwater_weekly"); nr = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM plots");              np = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM tubewells");          nt = cur.fetchone()["n"]
    conn.close()

    print("\n" + "=" * 60)
    print("Database fully seeded!")
    print(f"  Districts : {nd}")
    print(f"  Readings  : {nr}")
    print(f"  Plots     : {np}")
    print(f"  Tubewells : {nt}")
    print("=" * 60)


if __name__ == "__main__":
    main()
