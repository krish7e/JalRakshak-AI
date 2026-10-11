"""Proves the MySQL/RDS code path (schema, seed, queries) against a local
MySQL/MariaDB server.  Usage: python test_mysql_local.py HOST PORT [SOCKET]
Skips gracefully if no local server is available."""
import os, shutil, socket, subprocess, sys, time

def port_open(host, port):
    s = socket.socket(); s.settimeout(1)
    try: return s.connect_ex((host, port)) == 0
    finally: s.close()

def main():
    host, port = sys.argv[1], int(sys.argv[2])
    sock = sys.argv[3] if len(sys.argv) > 3 else None
    os.environ.update(DB_BACKEND="mysql", RDS_HOST=host, RDS_PORT=str(port),
                      RDS_USER="root", RDS_PASSWORD="", RDS_DATABASE="jalrakshak_test")
    if sock:
        import pymysql
        _orig = pymysql.connect
        def patched(*a, **kw):
            kw.pop("host"); kw["unix_socket"] = sock
            return _orig(*a, **kw)
        pymysql.connect = patched
    elif not port_open(host, port):
        print(f"SKIP: no MySQL on {host}:{port}")
        return 0

    import db
    be = db.get_backend()
    be.init_schema()
    from seed_data import DISTRICT_META, generate_weekly
    for d, m in DISTRICT_META.items():
        be.upsert_district({"district": d, **m})
    n = 0
    for d in DISTRICT_META:
        for r in generate_weekly(d)[:5]:   # first 5 weeks only, keep it quick
            be.put_reading(d, r["week"], r["date"], r["depth"]); n += 1
    assert be.count_districts() == 45, be.count_districts()
    assert be.count_readings() == n
    series = be.get_series("Ludhiana")
    assert len(series) == 5 and series[0]["week"] == 1
    be.put_reading("Ludhiana", 1, "2026-01-04", 99.99)      # upsert path
    assert be.get_series("Ludhiana")[0]["depth"] == 99.99
    assert len(be.list_districts("punjab")) == 23
    print("health:", be.health())
    print("MYSQL BACKEND LOGIC TESTS PASSED (45 districts, upsert+queries OK)")
    with be._conn() as c, c.cursor() as cur:
        cur.execute("DROP DATABASE jalrakshak_test")
    return 0

if __name__ == "__main__":
    sys.exit(main())
