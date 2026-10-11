"""
Unified data-access layer for JalRakshak AI.

Three interchangeable backends, chosen by the DB_BACKEND variable in .env:
  sqlite    -> Local zero-config SQLite file (default, runs instantly on any machine)
  mysql     -> Amazon RDS MySQL instance (needs RDS_HOST / RDS_USER / RDS_PASSWORD)
  dynamodb  -> Amazon DynamoDB tables (needs AWS_ACCESS_KEY_ID / SECRET or IAM role)

All backends expose the unified interface used by app.py and seed_data.py:
  health()
  init_schema()
  upsert_district(meta)
  list_districts(state=None)
  put_reading(district, week, date, depth)
  get_series(district)
  list_plots(district=None, state=None)
  upsert_plot(plot)
  delete_plot(plot_id)
  list_tubewells()
  toggle_tubewell(tubewell_id, new_status=None)
  get_settings()
  save_settings(settings_dict)
  count_readings()
  count_districts()
  count_plots()
  count_tubewells()
"""
import json
import os
import sqlite3
import threading
from decimal import Decimal
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

# Default to sqlite if DB_BACKEND is not specified or blank
BACKEND = (os.getenv("DB_BACKEND", "sqlite") or "sqlite").strip().lower()

TABLE_PREFIX = os.getenv("DYNAMODB_TABLE_PREFIX", "jalrakshak")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")
ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL") or None

GW_TABLE = f"{TABLE_PREFIX}-groundwater-weekly"
META_TABLE = f"{TABLE_PREFIX}-district-meta"


# --------------------------------------------------------------------------
# SQLite Backend (Default - Zero setup required)
# --------------------------------------------------------------------------
class SQLiteBackend:
    name = "sqlite"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv(
            "SQLITE_PATH",
            os.path.join(os.path.dirname(__file__), "jalrakshak.db")
        )
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return self._local.conn

    def health(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT sqlite_version()")
            ver = cur.fetchone()[0]
        return {
            "database": "sqlite",
            "path": os.path.abspath(self.db_path),
            "version": ver,
            "districts": self.count_districts(),
            "readings": self.count_readings(),
            "plots": self.count_plots(),
            "tubewells": self.count_tubewells()
        }

    def init_schema(self):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS districts (
                    district   TEXT PRIMARY KEY,
                    state      TEXT NOT NULL,
                    lat        REAL NOT NULL,
                    lng        REAL NOT NULL,
                    farms      INTEGER NOT NULL,
                    base_depth REAL NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS groundwater_weekly (
                    district     TEXT NOT NULL,
                    week         INTEGER NOT NULL,
                    reading_date TEXT,
                    depth_bgl    REAL NOT NULL,
                    PRIMARY KEY (district, week)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_gw_week ON groundwater_weekly(week)")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS plots (
                    id         TEXT PRIMARY KEY,
                    belt       TEXT NOT NULL,
                    district   TEXT NOT NULL,
                    state      TEXT NOT NULL,
                    owner      TEXT NOT NULL,
                    acres      REAL NOT NULL,
                    crop       TEXT NOT NULL,
                    stage      TEXT NOT NULL,
                    lat        REAL NOT NULL,
                    lng        REAL NOT NULL,
                    seed       INTEGER NOT NULL DEFAULT 10,
                    discharge  REAL NOT NULL DEFAULT 18.0,
                    runtime    REAL NOT NULL DEFAULT 6.0,
                    risk_level TEXT DEFAULT 'Normal'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tubewells (
                    id                 TEXT PRIMARY KEY,
                    plot_id            TEXT,
                    farmer_name        TEXT NOT NULL,
                    district           TEXT NOT NULL,
                    state              TEXT NOT NULL DEFAULT 'punjab',
                    lat                REAL NOT NULL,
                    lng                REAL NOT NULL,
                    depth              REAL NOT NULL,
                    discharge_lps      REAL NOT NULL,
                    status             TEXT NOT NULL DEFAULT 'IDLE',
                    running_hours      REAL NOT NULL DEFAULT 4.5,
                    power_kw           REAL NOT NULL DEFAULT 5.0,
                    daily_extraction_kl REAL NOT NULL DEFAULT 81.0,
                    feeder_window      TEXT DEFAULT 'morning',
                    last_updated       TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()

    def upsert_district(self, m: Dict[str, Any]):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO districts (district, state, lat, lng, farms, base_depth)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(district) DO UPDATE SET
                   state=excluded.state, lat=excluded.lat, lng=excluded.lng,
                   farms=excluded.farms, base_depth=excluded.base_depth""",
                (m["district"], m["state"], float(m["lat"]), float(m["lng"]),
                 int(m["farms"]), float(m["baseDepth"]))
            )
            conn.commit()

    def list_districts(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT district, state, lat, lng, farms, base_depth FROM districts"
        args = []
        if state and state != "all":
            query += " WHERE state = ?"
            args.append(state)
        query += " ORDER BY district"
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, args)
            rows = cur.fetchall()
        return [{
            "district": r["district"],
            "state": r["state"],
            "lat": float(r["lat"]),
            "lng": float(r["lng"]),
            "farms": int(r["farms"]),
            "baseDepth": float(r["base_depth"])
        } for r in rows]

    def put_reading(self, district: str, week: int, date: Optional[str], depth: float):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO groundwater_weekly (district, week, reading_date, depth_bgl)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(district, week) DO UPDATE SET
                   reading_date=excluded.reading_date, depth_bgl=excluded.depth_bgl""",
                (district, int(week), date or None, float(depth))
            )
            conn.commit()

    def get_series(self, district: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT week, reading_date, depth_bgl FROM groundwater_weekly
                   WHERE district = ? ORDER BY week ASC""",
                (district,)
            )
            rows = cur.fetchall()
        return [{
            "week": int(r["week"]),
            "date": r["reading_date"] or "",
            "depth": float(r["depth_bgl"])
        } for r in rows]

    def count_districts(self) -> int:
        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM districts")
                return int(cur.fetchone()[0])
        except Exception:
            return 0

    def count_readings(self) -> int:
        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM groundwater_weekly")
                return int(cur.fetchone()[0])
        except Exception:
            return 0

    def count_plots(self) -> int:
        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM plots")
                return int(cur.fetchone()[0])
        except Exception:
            return 0

    def count_tubewells(self) -> int:
        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM tubewells")
                return int(cur.fetchone()[0])
        except Exception:
            return 0

    def list_plots(self, district: Optional[str] = None, state: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM plots WHERE 1=1"
        args = []
        if district and district != "all":
            query += " AND district = ?"
            args.append(district)
        if state and state != "all":
            query += " AND state = ?"
            args.append(state)
        query += " ORDER BY id"
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, args)
            rows = cur.fetchall()
        return [{
            "id": r["id"],
            "belt": r["belt"],
            "district": r["district"],
            "state": r["state"],
            "owner": r["owner"],
            "acres": float(r["acres"]),
            "crop": r["crop"],
            "stage": r["stage"],
            "center": [float(r["lat"]), float(r["lng"])],
            "seed": int(r["seed"]),
            "discharge": float(r["discharge"]),
            "runtime": float(r["runtime"]),
            "riskLevel": r["risk_level"] or "Normal"
        } for r in rows]

    def upsert_plot(self, p: Dict[str, Any]):
        center = p.get("center", [p.get("lat", 30.0), p.get("lng", 75.0)])
        lat = center[0] if isinstance(center, (list, tuple)) and len(center) > 0 else float(p.get("lat", 30.0))
        lng = center[1] if isinstance(center, (list, tuple)) and len(center) > 1 else float(p.get("lng", 75.0))
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO plots (id, belt, district, state, owner, acres, crop, stage, lat, lng, seed, discharge, runtime, risk_level)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                   belt=excluded.belt, district=excluded.district, state=excluded.state,
                   owner=excluded.owner, acres=excluded.acres, crop=excluded.crop,
                   stage=excluded.stage, lat=excluded.lat, lng=excluded.lng,
                   seed=excluded.seed, discharge=excluded.discharge, runtime=excluded.runtime,
                   risk_level=excluded.risk_level""",
                (
                    p["id"], p.get("belt", p["district"]), p["district"], p["state"],
                    p["owner"], float(p["acres"]), p["crop"], p["stage"],
                    lat, lng, int(p.get("seed", 10)), float(p.get("discharge", 18.0)),
                    float(p.get("runtime", 6.0)), p.get("riskLevel", "Normal")
                )
            )
            conn.commit()

    def delete_plot(self, plot_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM plots WHERE id = ?", (plot_id,))
            conn.commit()
            return cur.rowcount > 0

    def list_tubewells(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM tubewells ORDER BY id")
            rows = cur.fetchall()
        return [{
            "id": r["id"],
            "plotId": r["plot_id"],
            "farmerName": r["farmer_name"],
            "district": r["district"],
            "state": r["state"],
            "lat": float(r["lat"]),
            "lng": float(r["lng"]),
            "depth": float(r["depth"]),
            "dischargeLps": float(r["discharge_lps"]),
            "status": r["status"],
            "runningHours": float(r["running_hours"]),
            "powerKw": float(r["power_kw"]),
            "dailyExtractionKl": float(r["daily_extraction_kl"]),
            "feederWindow": r["feeder_window"],
            "lastUpdated": r["last_updated"]
        } for r in rows]

    def toggle_tubewell(self, tubewell_id: str, new_status: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM tubewells WHERE id = ?", (tubewell_id,))
            row = cur.fetchone()
            if not row:
                return None
            current_status = row["status"]
            target_status = new_status or ("IDLE" if current_status == "RUNNING" else "RUNNING")
            cur.execute(
                """UPDATE tubewells SET status = ?, last_updated = datetime('now')
                   WHERE id = ?""",
                (target_status, tubewell_id)
            )
            conn.commit()
            cur.execute("SELECT * FROM tubewells WHERE id = ?", (tubewell_id,))
            updated = cur.fetchone()
            return {
                "id": updated["id"],
                "status": updated["status"],
                "lastUpdated": updated["last_updated"]
            }

    def upsert_tubewell(self, tw: Dict[str, Any]):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO tubewells (id, plot_id, farmer_name, district, state, lat, lng, depth, discharge_lps, status, running_hours, power_kw, daily_extraction_kl, feeder_window)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                   farmer_name=excluded.farmer_name, district=excluded.district,
                   depth=excluded.depth, discharge_lps=excluded.discharge_lps,
                   status=excluded.status, running_hours=excluded.running_hours,
                   power_kw=excluded.power_kw, daily_extraction_kl=excluded.daily_extraction_kl,
                   feeder_window=excluded.feeder_window""",
                (
                    tw["id"], tw.get("plotId"), tw["farmerName"], tw["district"],
                    tw.get("state", "punjab"), float(tw["lat"]), float(tw["lng"]),
                    float(tw["depth"]), float(tw["dischargeLps"]), tw.get("status", "IDLE"),
                    float(tw.get("runningHours", 4.5)), float(tw.get("powerKw", 5.0)),
                    float(tw.get("dailyExtractionKl", 81.0)), tw.get("feederWindow", "morning")
                )
            )
            conn.commit()

    def get_settings(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM settings")
            rows = cur.fetchall()
        out = {}
        for r in rows:
            try:
                out[r["key"]] = json.loads(r["value"])
            except Exception:
                out[r["key"]] = r["value"]
        return out

    def save_settings(self, settings_dict: Dict[str, Any]):
        with self._get_conn() as conn:
            for k, v in settings_dict.items():
                val_str = json.dumps(v) if isinstance(v, (dict, list, bool)) else str(v)
                conn.execute(
                    """INSERT INTO settings (key, value) VALUES (?, ?)
                       ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                    (k, val_str)
                )
            conn.commit()


# --------------------------------------------------------------------------
# DynamoDB Backend
# --------------------------------------------------------------------------
class DynamoBackend:
    name = "dynamodb"

    def __init__(self):
        import boto3
        from boto3.dynamodb.conditions import Key

        if ENDPOINT_URL:
            self._db = boto3.resource(
                "dynamodb",
                endpoint_url=ENDPOINT_URL,
                region_name=os.getenv("AWS_LOCAL_REGION", "us-east-1"),
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID") or "local",
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") or "local",
            )
        else:
            self._db = boto3.resource("dynamodb", region_name=AWS_REGION)
        self._Key = Key
        self.gw = self._db.Table(GW_TABLE)
        self.meta = self._db.Table(META_TABLE)

    def health(self):
        return {
            "database": "dynamodb",
            "region": ENDPOINT_URL or AWS_REGION,
            "tables": [GW_TABLE, META_TABLE],
            "tableStatus": getattr(self.gw, "table_status", "ACTIVE")
        }

    def init_schema(self):
        from botocore.exceptions import ClientError
        for name, pk, sk in ((GW_TABLE, "district", "week"), (META_TABLE, "district", None)):
            ks = [{"AttributeName": pk, "KeyType": "HASH"}]
            ad = [{"AttributeName": pk, "AttributeType": "S"}]
            if sk:
                ks.append({"AttributeName": sk, "KeyType": "RANGE"})
                ad.append({"AttributeName": sk, "AttributeType": "N"})
            try:
                self._db.create_table(TableName=name, KeySchema=ks, AttributeDefinitions=ad,
                                      BillingMode="PAY_PER_REQUEST")
                print(f"  created table: {name}")
                t = self._db.Table(name)
                t.wait_until_exists()
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceInUseException":
                    raise
                print(f"  table exists:  {name}")

    def upsert_district(self, m):
        self.meta.put_item(Item={
            "district": m["district"], "state": m["state"],
            "lat": Decimal(str(m["lat"])), "lng": Decimal(str(m["lng"])),
            "farms": int(m["farms"]), "baseDepth": Decimal(str(m["baseDepth"])),
        })

    def list_districts(self, state=None):
        out = []
        for m in self.meta.scan().get("Items", []):
            if state and state != "all" and m["state"] != state:
                continue
            out.append({"district": m["district"], "state": m["state"],
                        "lat": float(m["lat"]), "lng": float(m["lng"]),
                        "farms": int(m["farms"]), "baseDepth": float(m["baseDepth"])})
        return out

    def put_reading(self, district, week, date, depth):
        self.gw.put_item(Item={"district": district, "week": int(week),
                               "date": date or "", "depthBgl": Decimal(str(depth))})

    def get_series(self, district):
        resp = self.gw.query(KeyConditionExpression=self._Key("district").eq(district))
        items = sorted(resp.get("Items", []), key=lambda i: int(i["week"]))
        return [{"week": int(i["week"]), "date": i.get("date", ""), "depth": float(i["depthBgl"])}
                for i in items]

    def count_districts(self):
        try:
            return self.meta.scan(Select="COUNT").get("Count", 0)
        except Exception:
            return 0

    def count_readings(self):
        try:
            return self.gw.scan(Select="COUNT").get("Count", 0)
        except Exception:
            return 0

    def count_plots(self):
        return 0

    def count_tubewells(self):
        return 0

    def list_plots(self, district=None, state=None):
        return []

    def upsert_plot(self, p):
        pass

    def delete_plot(self, plot_id):
        return False

    def list_tubewells(self):
        return []

    def toggle_tubewell(self, tubewell_id, new_status=None):
        return None

    def upsert_tubewell(self, tw):
        pass

    def get_settings(self):
        return {}

    def save_settings(self, settings_dict):
        pass


# --------------------------------------------------------------------------
# RDS MySQL Backend
# --------------------------------------------------------------------------
class MySQLBackend:
    name = "mysql"

    def __init__(self):
        import pymysql
        self._pymysql = pymysql
        self.host = os.getenv("RDS_HOST", "")
        self.port = int(os.getenv("RDS_PORT", "3306"))
        self.user = os.getenv("RDS_USER", "admin")
        self.password = os.getenv("RDS_PASSWORD", "")
        self.database = os.getenv("RDS_DATABASE", "jalrakshak")

    def _conn(self, database=None):
        return self._pymysql.connect(
            host=self.host, port=self.port, user=self.user,
            password=self.password, database=database or self.database,
            connect_timeout=10, read_timeout=15, write_timeout=15,
            autocommit=True, charset="utf8mb4",
            cursorclass=self._pymysql.cursors.DictCursor,
        )

    def init_schema(self):
        import pymysql
        try:
            conn = self._conn()
        except pymysql.err.MySQLError:
            with self._conn(database=None) as c0, c0.cursor() as cur0:
                cur0.execute("CREATE DATABASE IF NOT EXISTS jalrakshak")
            self.database = "jalrakshak"
            conn = self._conn()

        with conn as c, c.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS districts (
                    district   VARCHAR(120) PRIMARY KEY,
                    state      VARCHAR(60)  NOT NULL,
                    lat        DECIMAL(9,6) NOT NULL,
                    lng        DECIMAL(9,6) NOT NULL,
                    farms      INT          NOT NULL,
                    base_depth DECIMAL(8,2) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS groundwater_weekly (
                    district   VARCHAR(120) NOT NULL,
                    week       INT          NOT NULL,
                    reading_date DATE       NULL,
                    depth_bgl  DECIMAL(8,2) NOT NULL,
                    PRIMARY KEY (district, week),
                    KEY idx_week (week)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS plots (
                    id         VARCHAR(50) PRIMARY KEY,
                    belt       VARCHAR(100) NOT NULL,
                    district   VARCHAR(120) NOT NULL,
                    state      VARCHAR(60)  NOT NULL,
                    owner      VARCHAR(120) NOT NULL,
                    acres      DECIMAL(6,2) NOT NULL,
                    crop       VARCHAR(60)  NOT NULL,
                    stage      VARCHAR(60)  NOT NULL,
                    lat        DECIMAL(9,6) NOT NULL,
                    lng        DECIMAL(9,6) NOT NULL,
                    seed       INT          NOT NULL DEFAULT 10,
                    discharge  DECIMAL(6,2) NOT NULL DEFAULT 18.0,
                    runtime    DECIMAL(6,2) NOT NULL DEFAULT 6.0,
                    risk_level VARCHAR(40)  DEFAULT 'Normal'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tubewells (
                    id                 VARCHAR(50) PRIMARY KEY,
                    plot_id            VARCHAR(50),
                    farmer_name        VARCHAR(120) NOT NULL,
                    district           VARCHAR(120) NOT NULL,
                    state              VARCHAR(60)  NOT NULL DEFAULT 'punjab',
                    lat                DECIMAL(9,6) NOT NULL,
                    lng                DECIMAL(9,6) NOT NULL,
                    depth              DECIMAL(8,2) NOT NULL,
                    discharge_lps      DECIMAL(6,2) NOT NULL,
                    status             VARCHAR(30)  NOT NULL DEFAULT 'IDLE',
                    running_hours      DECIMAL(6,2) NOT NULL DEFAULT 4.5,
                    power_kw           DECIMAL(6,2) NOT NULL DEFAULT 5.0,
                    daily_extraction_kl DECIMAL(8,2) NOT NULL DEFAULT 81.0,
                    feeder_window      VARCHAR(40)  DEFAULT 'morning',
                    last_updated       DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    `key`   VARCHAR(100) PRIMARY KEY,
                    `value` TEXT         NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

    def health(self):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT VERSION() AS v, DATABASE() AS d")
            r = cur.fetchone()
        return {"database": "mysql (Amazon RDS)", "host": self.host,
                "db": r["d"], "serverVersion": r["v"]}

    def upsert_district(self, m):
        with self._conn() as c, c.cursor() as cur:
            cur.execute(
                """INSERT INTO districts (district,state,lat,lng,farms,base_depth)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE state=VALUES(state), lat=VALUES(lat),
                   lng=VALUES(lng), farms=VALUES(farms), base_depth=VALUES(base_depth)""",
                (m["district"], m["state"], m["lat"], m["lng"],
                 int(m["farms"]), str(m["baseDepth"])))

    def list_districts(self, state=None):
        sql = "SELECT district, state, lat, lng, farms, base_depth FROM districts"
        args = []
        if state and state != "all":
            sql += " WHERE state=%s"
            args.append(state)
        sql += " ORDER BY district"
        with self._conn() as c, c.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
        return [{"district": r["district"], "state": r["state"],
                 "lat": float(r["lat"]), "lng": float(r["lng"]),
                 "farms": int(r["farms"]), "baseDepth": float(r["base_depth"])}
                for r in rows]

    def put_reading(self, district, week, date, depth):
        with self._conn() as c, c.cursor() as cur:
            cur.execute(
                """INSERT INTO groundwater_weekly (district, week, reading_date, depth_bgl)
                   VALUES (%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE reading_date=VALUES(reading_date),
                   depth_bgl=VALUES(depth_bgl)""",
                (district, int(week), date or None, str(depth)))

    def get_series(self, district):
        with self._conn() as c, c.cursor() as cur:
            cur.execute(
                "SELECT week, reading_date, depth_bgl FROM groundwater_weekly "
                "WHERE district=%s ORDER BY week", (district,))
            rows = cur.fetchall()
        return [{"week": int(r["week"]),
                 "date": r["reading_date"].strftime("%Y-%m-%d") if r["reading_date"] else "",
                 "depth": float(r["depth_bgl"])} for r in rows]

    def count_districts(self):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM districts")
            return int(cur.fetchone()["n"])

    def count_readings(self):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM groundwater_weekly")
            return int(cur.fetchone()["n"])

    def count_plots(self):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM plots")
            return int(cur.fetchone()["n"])

    def count_tubewells(self):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM tubewells")
            return int(cur.fetchone()["n"])

    def list_plots(self, district=None, state=None):
        sql = "SELECT * FROM plots WHERE 1=1"
        args = []
        if district and district != "all":
            sql += " AND district = %s"
            args.append(district)
        if state and state != "all":
            sql += " AND state = %s"
            args.append(state)
        sql += " ORDER BY id"
        with self._conn() as c, c.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
        return [{
            "id": r["id"], "belt": r["belt"], "district": r["district"],
            "state": r["state"], "owner": r["owner"], "acres": float(r["acres"]),
            "crop": r["crop"], "stage": r["stage"],
            "center": [float(r["lat"]), float(r["lng"])], "seed": int(r["seed"]),
            "discharge": float(r["discharge"]), "runtime": float(r["runtime"]),
            "riskLevel": r["risk_level"] or "Normal"
        } for r in rows]

    def upsert_plot(self, p):
        center = p.get("center", [p.get("lat", 30.0), p.get("lng", 75.0)])
        lat = center[0] if isinstance(center, (list, tuple)) and len(center) > 0 else float(p.get("lat", 30.0))
        lng = center[1] if isinstance(center, (list, tuple)) and len(center) > 1 else float(p.get("lng", 75.0))
        with self._conn() as c, c.cursor() as cur:
            cur.execute(
                """INSERT INTO plots (id, belt, district, state, owner, acres, crop, stage, lat, lng, seed, discharge, runtime, risk_level)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE belt=VALUES(belt), district=VALUES(district),
                   state=VALUES(state), owner=VALUES(owner), acres=VALUES(acres),
                   crop=VALUES(crop), stage=VALUES(stage), lat=VALUES(lat), lng=VALUES(lng),
                   seed=VALUES(seed), discharge=VALUES(discharge), runtime=VALUES(runtime),
                   risk_level=VALUES(risk_level)""",
                (p["id"], p.get("belt", p["district"]), p["district"], p["state"],
                 p["owner"], float(p["acres"]), p["crop"], p["stage"], lat, lng,
                 int(p.get("seed", 10)), float(p.get("discharge", 18.0)),
                 float(p.get("runtime", 6.0)), p.get("riskLevel", "Normal"))
            )

    def delete_plot(self, plot_id):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM plots WHERE id = %s", (plot_id,))
            return cur.rowcount > 0

    def list_tubewells(self):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT * FROM tubewells ORDER BY id")
            rows = cur.fetchall()
        return [{
            "id": r["id"], "plotId": r["plot_id"], "farmerName": r["farmer_name"],
            "district": r["district"], "state": r["state"], "lat": float(r["lat"]),
            "lng": float(r["lng"]), "depth": float(r["depth"]),
            "dischargeLps": float(r["discharge_lps"]), "status": r["status"],
            "runningHours": float(r["running_hours"]), "powerKw": float(r["power_kw"]),
            "dailyExtractionKl": float(r["daily_extraction_kl"]),
            "feederWindow": r["feeder_window"], "lastUpdated": str(r["last_updated"])
        } for r in rows]

    def toggle_tubewell(self, tubewell_id, new_status=None):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT status FROM tubewells WHERE id = %s", (tubewell_id,))
            row = cur.fetchone()
            if not row:
                return None
            target = new_status or ("IDLE" if row["status"] == "RUNNING" else "RUNNING")
            cur.execute(
                "UPDATE tubewells SET status = %s, last_updated = NOW() WHERE id = %s",
                (target, tubewell_id)
            )
            return {"id": tubewell_id, "status": target}

    def upsert_tubewell(self, tw):
        with self._conn() as c, c.cursor() as cur:
            cur.execute(
                """INSERT INTO tubewells (id, plot_id, farmer_name, district, state, lat, lng, depth, discharge_lps, status, running_hours, power_kw, daily_extraction_kl, feeder_window)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE farmer_name=VALUES(farmer_name),
                   district=VALUES(district), depth=VALUES(depth), discharge_lps=VALUES(discharge_lps),
                   status=VALUES(status), running_hours=VALUES(running_hours),
                   power_kw=VALUES(power_kw), daily_extraction_kl=VALUES(daily_extraction_kl),
                   feeder_window=VALUES(feeder_window)""",
                (tw["id"], tw.get("plotId"), tw["farmerName"], tw["district"],
                 tw.get("state", "punjab"), float(tw["lat"]), float(tw["lng"]),
                 float(tw["depth"]), float(tw["dischargeLps"]), tw.get("status", "IDLE"),
                 float(tw.get("runningHours", 4.5)), float(tw.get("powerKw", 5.0)),
                 float(tw.get("dailyExtractionKl", 81.0)), tw.get("feederWindow", "morning"))
            )

    def get_settings(self):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT `key`, `value` FROM settings")
            rows = cur.fetchall()
        out = {}
        for r in rows:
            try:
                out[r["key"]] = json.loads(r["value"])
            except Exception:
                out[r["key"]] = r["value"]
        return out

    def save_settings(self, settings_dict):
        with self._conn() as c, c.cursor() as cur:
            for k, v in settings_dict.items():
                val_str = json.dumps(v) if isinstance(v, (dict, list, bool)) else str(v)
                cur.execute(
                    "INSERT INTO settings (`key`, `value`) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE `value`=VALUES(`value`)",
                    (k, val_str)
                )


def get_backend():
    selected = BACKEND
    if selected == "mysql":
        return MySQLBackend()
    elif selected == "dynamodb":
        return DynamoBackend()
    else:
        return SQLiteBackend()
