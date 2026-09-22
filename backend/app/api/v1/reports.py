from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.fraud.ml import runner
from app.models import Alert, Transaction, User
from app.schemas import AlertStatus, TxnStatus, UserRole

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/fraud-trends")
def fraud_trends(
    days: int = Query(14, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST)),
):
    """Daily flagged + rejected transaction counts for the last N days."""
    start = datetime.now() - timedelta(days=days)
    rows = db.execute(
        select(
            func.date(Transaction.created_at).label("day"),
            Transaction.status,
            func.count(Transaction.id),
        )
        .where(Transaction.created_at >= start)
        .group_by("day", Transaction.status)
    ).all()
    labels = []
    flagged = []
    rejected = []
    days_map: dict[str, dict[str, int]] = {}
    for day, status, count in rows:
        days_map.setdefault(str(day), {"flagged": 0, "rejected": 0})[status.value] = int(count)
    for day in sorted(days_map):
        labels.append(day)
        flagged.append(days_map[day].get("flagged", 0))
        rejected.append(days_map[day].get("rejected", 0))
    return {"labels": labels, "flagged": flagged, "rejected": rejected}


@router.get("/volume")
def volume_report(
    days: int = Query(14, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Daily transaction volume and total value."""
    start = datetime.now() - timedelta(days=days)
    rows = db.execute(
        select(
            func.date(Transaction.created_at).label("day"),
            func.count(Transaction.id),
            func.sum(Transaction.amount),
        )
        .where(Transaction.created_at >= start)
        .group_by("day")
        .order_by("day")
    ).all()
    return {
        "labels": [str(d) for d, _, _ in rows],
        "counts": [int(c) for _, c, _ in rows],
        "values": [float(v or 0) for _, _, v in rows],
    }


@router.get("/model-metrics")
def model_metrics(_: User = Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST))):
    info = runner.info
    return {"available": bool(info), **({"info": info} if info else {})}


@router.get("/alert-throughput")
def alert_throughput(
    days: int = Query(14, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST)),
):
    start = datetime.now() - timedelta(days=days)
    status_counts = {
        s: db.execute(select(func.count(Alert.id)).where(Alert.status == s)).scalar()
        for s in AlertStatus
    }
    last_days = db.execute(
        select(func.date(Alert.created_at), func.count(Alert.id))
        .where(Alert.created_at >= start)
        .group_by(func.date(Alert.created_at))
        .order_by(func.date(Alert.created_at))
    ).all()
    return {
        "status_counts": {k.value: int(v or 0) for k, v in status_counts.items()},
        "daily": {"labels": [str(d) for d, _ in last_days], "values": [int(c) for _, c in last_days]},
    }