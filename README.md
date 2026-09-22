# Real-Time Fraud Detection & Transaction Monitoring System

A production-style simulation of a digital-banking transaction monitoring platform.
Detects suspicious activity using **rule-based + machine-learning** fraud detection,
computes a **0–100 risk score** in near real-time, and surfaces everything in an
investigation dashboard for fraud analysts and admins.

> Portfolio project — designed around real-world patterns: event streaming (Kafka),
> cache/velocity checks (Redis), ML risk scoring (LightGBM), and full audit trails.

## Stack

| Layer       | Tech                                                          |
|-------------|---------------------------------------------------------------|
| Frontend    | Next.js + TypeScript + Tailwind CSS + Recharts                |
| Backend API | Python + FastAPI (REST, SSE/WebSocket real-time feeds)        |
| Database    | PostgreSQL                                                    |
| Cache       | Redis (velocity counters, rate limiting, pub/sub)             |
| Streaming   | Kafka (replayable transaction event backbone, KRaft)          |
| ML          | scikit-learn / LightGBM feature pipeline + model registry     |
| Infra       | Docker + Docker Compose                                       |

## Features

- User / account / device management with JWT auth + RBAC (customer, analyst, admin)
- Transaction ingestion with synchronous rule+ML fast-path decision
- Rule engine: velocity, amount-spike, geo-speed, failed-attempt, new-device/location, odd-hours
- ML fraud probability (LightGBM), calibrated + SHAP-explainable
- Fusion risk score 0–100 with decision policy (APPROVE / REVIEW / BLOCK)
- Suspicious-transaction alerts + investigation workflow
- Customer/account risk profiling
- Audit/activity logs, admin dashboards, reports & analytics
- Synthetic transaction data generator for demo/load testing

## Architecture

```
Frontend (Next.js) ──► FastAPI ──► Kafka ──► Fraud Engine (rules + ML) ──► decision
                        │  ▲                     │
                        ▼  │                     ▼
                  PostgreSQL · Redis     alerts / audit / risk profiles
```

- **Sync leg:** instant risk decision returned in the HTTP response (fast path).
- **Async leg:** Kafka consumers run the deep pipeline — full features, alerts,
  risk-profile updates, SHAP explainability, and model-retraining data.

## Folder Layout

```
├── backend/        FastAPI services, fraud engine, workers, ML training
├── frontend/       Next.js app (customer / analyst / admin dashboards)
├── infra/          nginx, prometheus, grafana configs
├── docker-compose.yml
└── .env.example
```

## Getting Started

> Requires Docker + Docker Compose (or run each stack locally).

```bash
cp .env.example .env
docker compose up --build
# API     → http://localhost:8000 (docs at /docs)
# Frontend→ http://localhost:3000
```

On first boot the API seeds demo data idempotently (a small rule set plus demo
accounts). An ML artifact ships already-trained in `backend/ml/artifacts/`; to
retrain on the running database:

```bash
docker compose exec backend python3 -m app.ml.training.train
```

To push a burst of synthetic transactions (triggers live alerts in the UI):

```bash
docker compose exec backend python3 scripts/simulate.py --burst 200 --fraud-rate 0.2
```

### Demo credentials

| Role       | Username | Password      |
|------------|----------|---------------|
| Customer   | `alice`  | `password123` |
| Analyst    | `analyst`| `password123` |
| Admin      | `admin`  | `password123` |

### Local dev (no Docker)

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Roadmap / Phases

| Phase | Scope |
|-------|-------|
| 0  | Scaffold, infra, base configs            |
| 1  | Core API: auth, users, accounts, transactions |
| 2  | Rule-based fraud engine + Redis velocity  |
| 3  | Kafka event flow + async pipeline + alerts |
| 4  | ML pipeline (LightGBM/RandomForest) + risk fusion |
| 5  | Frontend dashboards + real-time feeds     |
| 6  | Reports, analytics, hardening, load test     |

All phases are implemented. Tests: `cd backend && python -m pytest` (22 passing).