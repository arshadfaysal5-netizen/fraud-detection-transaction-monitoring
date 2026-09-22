import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.v1 import (
    accounts,
    admin,
    alerts,
    auth,
    health,
    metrics,
    reports,
    stream,
    transactions,
    users,
)
from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.events import hub
from app.core.kafka import bus
from app.core.logging import setup_logging
from app.models import Rule


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()

    # Seed default rules + demo users (idempotent)
    db = SessionLocal()
    try:
        from scripts.seed import seed_rules, seed_users_and_accounts

        if db.execute(select(Rule).limit(1)).scalar_one_or_none() is None:
            seed_rules(db)
        seed_users_and_accounts(db)
    finally:
        db.close()

    hub.attach(asyncio.get_running_loop())
    bus.start()

    # Async deep pipeline (no-op when Kafka unreachable)
    worker_task = asyncio.create_task(_run_worker())
    yield
    worker_task.cancel()


async def _run_worker() -> None:
    from app.workers.consumers import run_consumer

    await run_consumer()


app = FastAPI(
    title="Fraud Detection & Transaction Monitoring API",
    description=(
        "Real-time digital-banking transaction monitoring with rule-based and "
        "machine-learning fraud detection, 0-100 risk scoring, alerting and "
        "investigation tooling."
    ),
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_V1_PREFIX = "/api/v1"

app.include_router(health.router, prefix=API_V1_PREFIX)
app.include_router(auth.router, prefix=API_V1_PREFIX)
app.include_router(users.router, prefix=API_V1_PREFIX)
app.include_router(accounts.router, prefix=API_V1_PREFIX)
app.include_router(transactions.router, prefix=API_V1_PREFIX)
app.include_router(alerts.router, prefix=API_V1_PREFIX)
app.include_router(admin.router, prefix=API_V1_PREFIX)
app.include_router(stream.router, prefix=API_V1_PREFIX)
app.include_router(reports.router, prefix=API_V1_PREFIX)
app.include_router(metrics.router)  # root-level for prometheus scraping


@app.get("/health", tags=["ops"], include_in_schema=False)
async def root_health() -> dict:
    return {"status": "ok", "service": "fraud-backend"}