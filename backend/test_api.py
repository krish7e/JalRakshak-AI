"""
End-to-end test for the JalRakshak AI DynamoDB backend.

Seeds the tables inside a moto (in-memory AWS) mock, then exercises every
FastAPI endpoint through the app's real boto3 code path. Also verifies the
seeded weekly depths match the JS formula in index.html.

Run:  python -m pytest test_api.py -q     (or: python test_api.py)
"""
import math
import os

# Force dummy creds BEFORE importing anything that builds a client.
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["DYNAMODB_ENDPOINT_URL"] = ""          # use mocked AWS API, not localhost
os.environ["DYNAMODB_TABLE_PREFIX"] = "jalrakshak-test"

from fastapi.testclient import TestClient
from moto import mock_aws


def _patch_env(module):
    """backend/.env may select mysql or point at DynamoDB Local; tests run fully in-memory (moto)."""
    module.BACKEND = "dynamodb"
    module.ENDPOINT_URL = None
    module.TABLE_PREFIX = "jalrakshak-test"
    module.GW_TABLE = "jalrakshak-test-groundwater-weekly"
    module.META_TABLE = "jalrakshak-test-district-meta"


def js_expected_depth(base_depth: float, w: int) -> float:
    """Independent re-implementation of the index.html formula for cross-checking."""
    if 14 <= w <= 22:
        seasonal = (w - 14) * 0.35
    elif 23 <= w <= 35:
        seasonal = 8 * 0.35 - (w - 23) * 0.15
    elif w > 35:
        seasonal = max(0, 8 * 0.35 - 12 * 0.15 - (w - 35) * 0.2)
    else:
        seasonal = 0
    noise = math.sin(w * 1.7 + base_depth) * 0.4 + math.cos(w * 0.9) * 0.3
    return round(base_depth + seasonal + noise, 2)


@mock_aws
def run():
    import db as dbmod
    _patch_env(dbmod)           # force dynamodb backend, test table names
    import seed_data
    seed_data.main([])          # ENDPOINT_URL None -> boto3 hits the moto mock

    class _TestBackend(dbmod.DynamoBackend):
        def __init__(self):
            import boto3
            from boto3.dynamodb.conditions import Key
            self._Key = Key
            self._db = boto3.resource("dynamodb", region_name="us-east-1")
            self.gw = self._db.Table(dbmod.GW_TABLE)
            self.meta = self._db.Table(dbmod.META_TABLE)

    import app as api_app
    api_app._ddb = _TestBackend()
    client = TestClient(api_app.app)

    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    print("health:", r.json())

    r = client.get("/api/districts")
    assert r.status_code == 200 and r.json()["count"] == 45, r.text
    r2 = client.get("/api/districts", params={"state": "punjab"})
    assert r2.json()["count"] == 23, r2.text
    print("districts: 45 total, 23 punjab OK")

    r = client.get("/api/groundwater/latest")
    data = r.json()
    assert data["count"] == 45
    top = data["districts"][0]
    assert top["depth"] >= data["districts"][-1]["depth"]  # sorted desc
    print(f"latest: {data['count']} districts; deepest={top['name']} {top['depth']} m bgl ({top['stress']['level']})")

    r = client.get("/api/groundwater/Mahendragarh")
    d = r.json()
    assert len(d["series"]) == 41
    # cross-check against the JS formula
    for row in d["series"]:
        expected = js_expected_depth(48.54, row["week"])
        assert abs(row["depth"] - expected) < 0.011, (row, expected)
    print(f"Mahendragarh series matches index.html formula exactly (41 weeks)")
    print("velocity:", d["velocity"], "| stress:", d["stress"]["statusLabel"])

    r = client.post("/api/groundwater/Ludhiana", json={"week": 42, "date": "2026-10-11", "depthBgl": 36.42})
    assert r.status_code == 200, r.text
    d = client.get("/api/groundwater/Ludhiana").json()
    assert d["series"][-1]["week"] == 42 and d["series"][-1]["depth"] == 36.42
    print("POST new reading -> readable back from DynamoDB OK")

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run()
