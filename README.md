# JalRakshak AI — Groundwater Intelligence & Smart Irrigation Platform

> **AI-Powered Groundwater Monitoring, Satellite Fusion & Smart Tubewell Optimization Platform for Punjab & Haryana.**

---

## 🌟 Overview

**JalRakshak AI** is an end-to-end water intelligence and irrigation management platform. It solves the critical challenge of connecting rich frontend dashboards with real, persistent databases without complex setup.

### 🎯 Key Highlights
- **Unified Dual-Backend Architecture**: Run seamlessly using either **Node.js** (`npm start`) or **Python FastAPI** (`python backend/app.py`). Both connect to the exact same database!
- **Zero-Config Local SQLite Database**: Runs out of the box on any computer without needing external database servers or cloud accounts.
- **Switchable Cloud Databases**: Seamlessly switch between **Local SQLite**, **Amazon RDS (MySQL)**, or **Amazon DynamoDB** by changing one variable in `.env`.
- **Automatic Database Seeding**: Auto-initializes on startup with 45 districts (Punjab & Haryana), 1,845 weekly groundwater readings, 24 registered farm plots, and 12 smart tubewell stations.
- **Full Frontend Database Integration**: The single-page dashboard (`index.html`) is equipped with an auto-detecting client layer (`JalRakshakAPI`) with live connection indicators, plot creation modal, settings persistence, and smooth offline fallback.

---

## 🏗️ Architecture

```
                       ┌───────────────────────────────┐
                       │     index.html (Dashboard)    │
                       │  (Leaflet, Chart.js, Tailwind)│
                       └───────────────┬───────────────┘
                                       │ REST API (/api/*)
                   ┌───────────────────┴───────────────────┐
                   ▼                                       ▼
      ┌─────────────────────────┐             ┌─────────────────────────┐
      │   Node.js Backend       │             │   Python FastAPI        │
      │   (server.js - :3000)   │             │ (backend/app.py - :8001)│
      └────────────┬────────────┘             └────────────┬────────────┘
                   │                                       │
                   └───────────────────┬───────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
┌──────────────────┐          ┌──────────────────┐          ┌──────────────────┐
│  SQLite File     │          │  Amazon RDS      │          │  Amazon DynamoDB │
│  (jalrakshak.db) │          │  (MySQL/MariaDB) │          │  (AWS NoSQL)     │
│  [Default / Free]│          │  [DB_BACKEND]    │          │  [DB_BACKEND]    │
└──────────────────┘          └──────────────────┘          └──────────────────┘
```

---

## 🚀 Quick Start

You can run the project using **Node.js** OR **Python** — choose whichever you prefer:

### Option A: Run with Node.js (Recommended - Zero Dependencies)
Node.js v22 comes with built-in SQLite support. No `npm install` required!

```bash
# Start the server (Port 3000)
npm start
# or: node server.js
```
Open **`http://localhost:3000`** in your browser. The dashboard is automatically connected to the SQLite database!

---

### Option B: Run with Python FastAPI
```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Run diagnostics (verifies database)
python connect_check.py

# 3. Start the FastAPI server (Port 8001)
python app.py
# or: uvicorn app:app --port 8001 --reload
```
Open **`http://localhost:8001`** in your browser (or open `index.html` directly).

---

## 🗄️ Database Options

The active database is controlled by `DB_BACKEND` in `backend/.env`:

| `DB_BACKEND` | Engine | Setup Required | Best For |
|---|---|---|---|
| `sqlite` *(Default)* | **SQLite** (`backend/jalrakshak.db`) | **None** (auto-creates & seeds) | Local development, testing, hackathons |
| `mysql` | **Amazon RDS MySQL** | `RDS_HOST`, `RDS_USER`, `RDS_PASSWORD` | Production relational deployment |
| `dynamodb` | **Amazon DynamoDB** | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Serverless cloud deployment |

### Switching Databases
Create `backend/.env` (from `backend/.env.example`):
```ini
# Default local SQLite:
DB_BACKEND=sqlite

# To use Amazon RDS MySQL:
# DB_BACKEND=mysql
# RDS_HOST=your-rds-endpoint.rds.amazonaws.com
# RDS_USER=admin
# RDS_PASSWORD=your_password
# RDS_DATABASE=jalrakshak
```

---

## 📡 REST API Reference

All endpoints return JSON and support CORS.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Live database health, engine type, and entity counts |
| `GET` | `/api/districts` | List 45 monitored districts (`?state=punjab` or `?state=haryana`) |
| `GET` | `/api/groundwater/latest` | Latest week depth, stress category, velocity & extraction |
| `GET` | `/api/groundwater/{district}` | Full 41-week historical groundwater series for a district |
| `POST` | `/api/groundwater/{district}` | Submit a new weekly groundwater depth reading |
| `GET` | `/api/registry/plots` | List registered growers and agricultural plots |
| `POST` | `/api/registry/plots` | Register a new farm plot (saves to database) |
| `DELETE` | `/api/registry/plots/{id}` | Delete a registered farm plot |
| `GET` | `/api/tubewells` | List smart tubewells with status, power, and extraction |
| `POST` | `/api/tubewells/{id}/toggle` | Remotely toggle tubewell pump status (`RUNNING` / `IDLE`) |
| `GET` | `/api/planner/calculate` | Irrigation budget and optimal runtime calculation |
| `GET` | `/api/settings` | Retrieve water budget thresholds & alert preferences |
| `POST` | `/api/settings` | Save and persist platform threshold & alert preferences |
| `POST` | `/api/database/seed` | Re-seed and synchronize database entities |

---

## 🧪 Testing

Run automated integration tests verifying API formulas and database operations:

```bash
# Python test suite:
python backend/test_api.py

# Health verification:
python backend/connect_check.py
```

---

## 📂 Project Structure

```
JalRakshak-AI/
├── index.html            # Main frontend command center (HTML5 + CSS + JS)
├── server.js             # Node.js zero-dependency backend & static server
├── package.json          # Node.js project scripts
├── backend/
│   ├── app.py            # FastAPI service with complete REST API
│   ├── db.py             # Data access layer (SQLite, MySQL, DynamoDB)
│   ├── seed_data.py      # Seed script (45 districts, 1845 readings, plots, pumps)
│   ├── connect_check.py  # Health and connection diagnostics
│   ├── test_api.py       # Integration test suite
│   ├── requirements.txt  # Python requirements
│   ├── .env.example      # Environment variables template
│   └── jalrakshak.db     # Local SQLite database (auto-generated)
└── README.md
```

---

## 📜 License
MIT License. Built for agricultural sustainability and groundwater preservation.