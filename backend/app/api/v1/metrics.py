"""Minimal prometheus-style metrics endpoint (optional hardening)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select

from app.core.db import get_db

router = APIRouter(tags=["ops"])


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics(request: Request, db=Depends(get_db)):
    try:
        from app.models import Alert, Transaction

        total = db.execute(select(func.count(Transaction.id))).scalar() or 0
        alerts = db.execute(select(func.count(Alert.id))).scalar() or 0
        flagged = db.execute(
            select(func.count(Transaction.id)).where(Transaction.status == "flagged")
        ).scalar() or 0
    except Exception:
        total = alerts = flagged = 0

    body = "\n".join(
        [
            "# HELP fraud_transactions_total Total transactions recorded",
            "# TYPE fraud_transactions_total gauge",
            f"fraud_transactions_total {total}",
            "# HELP fraud_alerts_total Total alerts raised",
            "# TYPE fraud_alerts_total gauge",
            f"fraud_alerts_total {alerts}",
            "# HELP fraud_flagged_transactions_total Flagged transactions",
            "# TYPE fraud_flagged_transactions_total gauge",
            f"fraud_flagged_transactions_total {flagged}",
            f"fraud_uptime_seconds {int((datetime.now() - request.app.state._startup).total_seconds()) if hasattr(request.app.state, '_startup') else 0}",
        ]
    )
    return PlainTextResponse(body)