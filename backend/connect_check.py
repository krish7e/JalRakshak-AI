"""
One-shot connectivity check for JalRakshak AI database backend.

Usage:
  python connect_check.py                     # checks configured backend (default: sqlite)
  DB_BACKEND=mysql python connect_check.py    # checks RDS MySQL
  DB_BACKEND=dynamodb python connect_check.py # checks DynamoDB
"""
import os
import sys
import time
from db import get_backend, BACKEND


def main():
    print(f"Backend selected by environment: {BACKEND}")

    if BACKEND == "mysql":
        host = os.getenv("RDS_HOST", "")
        print(f"Checking MySQL endpoint: {host} ...")
        try:
            ip = __import__("socket").gethostbyname(host)
            print(f"DNS resolved: {host} -> {ip}")
            private = ip.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                                     "172.2", "172.30.", "172.31.", "192.168."))
            if private:
                print("Note: Endpoint resolves to a private VPC IP. Ensure RDS is publicly accessible")
                print("      or execute within the AWS VPC.")
        except Exception as e:
            print(f"DNS resolution warning: {e}")

    t = time.time()
    try:
        be = get_backend()
        info = be.health()
        elapsed = time.time() - t
        print(f"[SUCCESS] Connected in {elapsed:.2f}s -> {info}")
        try:
            print(f"Database contents:")
            print(f"  - Districts: {be.count_districts()}")
            print(f"  - Readings:  {be.count_readings()}")
            print(f"  - Plots:     {be.count_plots()}")
            print(f"  - Tubewells: {be.count_tubewells()}")
        except Exception as e:
            print(f"Note: Tables empty or uninitialized? Run `python seed_data.py`: {e}")
        return 0
    except Exception as e:
        elapsed = time.time() - t
        print(f"[FAILED] Connection failed after {elapsed:.2f}s: {type(e).__name__}: {str(e)[:300]}")
        if BACKEND == "dynamodb":
            print("Troubleshooting DynamoDB:")
            print("  - Provide AWS_ACCESS_KEY_ID & AWS_SECRET_ACCESS_KEY in .env, OR")
            print("  - Set DB_BACKEND=sqlite for zero-config offline development.")
        elif BACKEND == "mysql":
            print("Troubleshooting MySQL:")
            print("  - Verify RDS security group port 3306 and Public Accessibility.")
            print("  - Set DB_BACKEND=sqlite for zero-config offline development.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
