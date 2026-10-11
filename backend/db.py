"""
Unified data-access layer for JalRakshak AI.

Two interchangeable backends, chosen by the DB_BACKEND variable in .env:

  dynamodb  -> Amazon DynamoDB tables (needs AWS_ACCESS_KEY_ID / SECRET or IAM role)
  mysql     -> Amazon RDS MySQL instance (needs RDS_HOST / RDS_USER / RDS_PASSWORD)

Both expose the same interface used by app.py and seed_data.py:

  health()                  -> dict describing the live connection
  upsert_district(meta)     -> insert/update one district row
  list_districts(state=None)-> list of district dicts
  put_reading(district, week, date, depth)
  get_series(district)      -> [{week:int, date:str, depth:float}, ...] sorted by week
  init_schema()             -> create database/tables if missing (idempotent)
  count_readings()/count_districts()
"""
import os
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

BACKEND = (os.getenv("DB_BACKEND", "dynamodb") or "dynamodb").strip().lower()

TABLE_PREFIX = os.getenv("DYNAMODB_TABLE_PREFIX", "jalrakshak")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")
ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL") or None

GW_TABLE = f"{TABLE_PREFIX}-groundwater-weekly"
META_TABLE = f"{TABLE_PREFIX}-district-meta"


# --------------------------------------------------------------------------
# DynamoDB backend
# --------------------------------------------------------------------------
class DynamoBackend:
    name = "dynamodb"

    def __init__(self):
        import boto3
        from boto3.dynamodb.conditions import Key  # noqa: F401 (kept for API parity)

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
        return {"database": "dynamodb", "region": ENDPOINT_URL or AWS_REGION,
                "tables": [GW_TABLE, META_TABLE], "tableStatus": self.gw.table_status}

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
        return [{"week": int(i["week"]), "date": i["date"], "depth": float(i["depthBgl"])}
                for i in items]

    def count_districts(self):
        return self.meta.scan(Select="COUNT")["Count"]

    def count_readings(self):
        return self.gw.scan(Select="COUNT")["Count"]


# --------------------------------------------------------------------------
# RDS MySQL backend
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
            connect_timeout=15, read_timeout=30, write_timeout=30,
            autocommit=True, charset="utf8mb4",
            cursorclass=self._pymysql.cursors.DictCursor,
        )

    def init_schema(self):
        # try to create the database; if the RDS master user lacks CREATEDB,
        # fall back to an existing database on the instance.
        import pymysql
        try:
            conn = self._conn()
        except pymysql.err.MySQLError:
            with self._conn(database=None) as c0, c0.cursor() as cur0:
                cur0.execute("SHOW DATABASES")
                names = [r[list(r.keys())[0]] for r in cur0.fetchall()]
                for cand in ("jalrakshak", "app", "application", "admin"):
                    if cand in names:
                        self.database = cand
                        print(f"  using existing database: {cand}")
                        break
                else:
                    raise
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
        print(f"  schema ready in MySQL db `{self.database}` "
              f"(tables: districts, groundwater_weekly)")

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
        sql = ("SELECT district, state, lat, lng, farms, base_depth "
               "FROM districts{where} ORDER BY district")
        args = ()
        if state and state != "all":
            sql = sql.replace("{where}", " WHERE state=%s")
            args = (state,)
        else:
            sql = sql.replace("{where}", "")
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
            cur.execute("SELECT COUNT(*) n FROM districts")
            return int(cur.fetchone()["n"])

    def count_readings(self):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM groundwater_weekly")
            return int(cur.fetchone()["n"])


def get_backend():
    if BACKEND == "mysql":
        return MySQLBackend()
    return DynamoBackend()
