# JalRakshak AI — Backend (AWS database environment)

FastAPI backend for the `index.html` dashboard with a **switchable AWS data store**.
One variable in `.env` chooses the database:

| `DB_BACKEND` | What it connects to | Credentials needed in `.env` |
|---|---|---|
| `mysql` (current) | **Amazon RDS MySQL** instance `jalrakshak...rds.amazonaws.com` | `RDS_USER` / `RDS_PASSWORD` |
| `dynamodb` | **Amazon DynamoDB** tables (`jalrakshak-groundwater-weekly`, `jalrakshak-district-meta`) | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (+ region) |
| either + `DYNAMODB_ENDPOINT_URL=http://localhost:8000` | DynamoDB Local for offline dev | none (dummy values ok) |

> ⚠️ IMPORTANT — your endpoint is RDS, not DynamoDB.
> `jalrakshak.claygkmqe1sb.ap-southeast-2.rds.amazonaws.com` is an **Amazon RDS
> (MySQL/MariaDB) DB instance** — DynamoDB has no per-account hostname and no
> master username/password like this. The environment therefore supports BOTH:
> your RDS credentials are wired in as the `mysql` backend today, and you can flip
> to real DynamoDB by changing one line. See "Important correction" below.

## Files
- `db.py` — unified data layer; `DynamoBackend` and `MySQLBackend` share one interface
- `app.py` — FastAPI API (health / districts / groundwater latest / series / POST reading)
- `seed_data.py` — creates schema + loads the exact 45-district × 41-week dataset from `index.html` (works on whichever backend is selected)
- `connect_check.py` — one-shot connectivity test with actionable diagnostics
- `test_api.py` — end-to-end tests against in-memory DynamoDB (moto)
- `.env` — live config (gitignored), `.env.example` — template

## Quick start (current setup: RDS MySQL)
```bash
cd backend
pip install -r requirements.txt
python connect_check.py     # verifies the RDS connection & shows row counts
python seed_data.py         # creates jalrakshak db + tables + 1,845 readings
uvicorn app:app --reload --port 8001
curl http://localhost:8001/api/health   # -> {"database":"mysql (Amazon RDS)", ...}
```

## If `connect_check.py` says "timed out" (the usual RDS blocker)
The endpoint currently resolves to a **private VPC IP (172.31.x.x)**, so only
resources inside that VPC can reach it. To connect from your laptop:
1. AWS Console → **RDS → jalrakshak instance → Modify → Networking →
   "Publicly accessible" = Yes** → Apply immediately.
2. **Security group inbound rule**: MySQL/Aurora port **3306** source = *your* IP
   (e.g. `x.x.x.x/32`). Never leave `0.0.0.0/0` open permanently.
3. Re-run `python connect_check.py`.
(Alternatively deploy `backend/` on an EC2/Lambda inside the same VPC + security group.)

## Switching to real Amazon DynamoDB
1. `.env`: set `DB_BACKEND=dynamodb`, fill `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION=ap-southeast-2`.
2. IAM policy for the key: `dynamodb:PutItem/GetItem/Query/Scan/CreateTable/DescribeTable`
   on `arn:aws:dynamodb:*:*:table/jalrakshak-*`.
3. `python seed_data.py` then `uvicorn app:app --port 8001`.

## Offline development without AWS
```bash
docker run -d -p 8000:8000 amazon/dynamodb-local
# .env: DB_BACKEND=dynamodb  DYNAMODB_ENDPOINT_URL=http://localhost:8000
python seed_data.py && uvicorn app:app --port 8001
python test_api.py           # fully mocked, no network needed
```

## API endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | live DB connectivity check (shows active backend) |
| GET | `/api/districts?state=punjab` | district metadata |
| GET | `/api/groundwater/latest` | latest depth/stress/velocity for all districts |
| GET | `/api/groundwater/{district}` | full weekly series for one district |
| POST | `/api/groundwater/{district}` | write `{week, date?, depthBgl}` (upsert) |

## Security notes
- `.env` holds the RDS master password and is gitignored — never commit it.
- Consider rotating the password you shared in chat, since it was pasted in plaintext.
- Prefer a dedicated non-master DB user for the app in production.
