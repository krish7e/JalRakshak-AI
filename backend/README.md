# JalRakshak AI — Backend Service

FastAPI backend for JalRakshak AI with a **switchable multi-database architecture**:

| `DB_BACKEND` | Storage Engine | Prerequisites | Best For |
|---|---|---|---|
| `sqlite` *(default)* | **Local SQLite** (`jalrakshak.db`) | None (auto-creates & seeds) | Offline development, local testing |
| `mysql` | **Amazon RDS MySQL** instance | `RDS_HOST`, `RDS_USER`, `RDS_PASSWORD` | Cloud production |
| `dynamodb` | **Amazon DynamoDB** tables | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | AWS serverless |

---

## ⚡ Quick Start (Default Local SQLite - Zero AWS Setup Required)

```bash
cd backend
pip install -r requirements.txt
python connect_check.py     # verifies connectivity & counts
python app.py               # runs server on http://localhost:8001
```

Visit **`http://localhost:8001/`** to view the live dashboard or **`http://localhost:8001/docs`** for interactive Swagger documentation.

---

## 📦 Files

- `app.py` — FastAPI service (districts, groundwater series, farm registry, tubewell control, planner, settings)
- `db.py` — Unified data layer supporting `SQLiteBackend`, `MySQLBackend`, and `DynamoBackend`
- `seed_data.py` — Database seeder (45 districts, 1,845 weekly readings, 24 farm plots, 12 tubewells, settings)
- `connect_check.py` — Quick connection & health diagnostics
- `test_api.py` — Automated integration test suite
- `.env.example` — Configuration template
- `requirements.txt` — Python dependencies

---

## 🔄 Switching to Amazon RDS MySQL or DynamoDB

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Set `DB_BACKEND=mysql` and add your RDS credentials, or set `DB_BACKEND=dynamodb` and add AWS credentials.
3. Verify connection:
   ```bash
   python connect_check.py
   ```
4. If switching to a fresh database, run:
   ```bash
   python seed_data.py
   ```
