"""One-shot connectivity check for whichever DB_BACKEND is set in .env.

Usage:  python connect_check.py            # uses .env (currently mysql/RDS)
        DB_BACKEND=dynamodb python connect_check.py
"""
import os, sys, time
from db import get_backend, BACKEND


def main():
    print(f"Backend selected by .env: {BACKEND}")
    if BACKEND == "mysql":
        host = os.getenv("RDS_HOST", "")
        try:
            ip = __import__("socket").gethostbyname(host)
            print(f"DNS ok: {host} -> {ip}")
            private = ip.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                                     "172.2", "172.30.", "172.31.", "192.168."))
            if private:
                print("WARNING: endpoint resolves to a PRIVATE VPC address. This machine is")
                print("         outside that VPC, so the connection will hang/fail unless the")
                print("         RDS instance is 'Publicly accessible = yes' AND its security")
                print("         group allows port 3306 from this network.")
        except Exception as e:
            print(f"DNS FAILED: {e}")
            return 2

    t = time.time()
    try:
        be = get_backend()
        info = be.health()
        print(f"CONNECTED in {time.time()-t:.1f}s -> {info}")
        try:
            print(f"data present: {be.count_districts()} districts, {be.count_readings()} readings")
        except Exception as e:
            print(f"(tables empty/missing? run `python seed_data.py`) -> {str(e)[:150]}")
        return 0
    except Exception as e:
        print(f"CONNECTION FAILED after {time.time()-t:.1f}s: {type(e).__name__}: {str(e)[:300]}")
        if BACKEND == "mysql":
            print("""
Fix options (AWS Console -> RDS -> your 'jalrakshak' instance):
  1. Configuration -> make sure 'Publicly accessible' = Yes  (Modify + Apply immediately)
  2. Security -> inbound rule for port 3306 from your IP (or 0.0.0.0/0 for testing)
  3. If it still fails, run this backend on an EC2 inside the same VPC/security group.
To use real DynamoDB instead: set DB_BACKEND=dynamodb and add AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY in .env, then run: python seed_data.py""")
        return 1


if __name__ == "__main__":
    sys.exit(main())
