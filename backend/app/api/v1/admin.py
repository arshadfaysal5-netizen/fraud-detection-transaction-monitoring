import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.fraud.ml import runner
from app.models import Account, Alert, Rule, Transaction, User
from app.schemas import TxnStatus, UserRole
from app.schemas.alert import AlertOut
from app.services.audit_service import record_audit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    txn_count = db.execute(select(func.count(Transaction.id))).scalar()
    flagged = db.execute(
        select(func.count(Transaction.id)).where(Transaction.status == TxnStatus.FLAGGED)
    ).scalar()
    rejected = db.execute(
        select(func.count(Transaction.id)).where(Transaction.status == TxnStatus.REJECTED)
    ).scalar()
    users = db.execute(select(func.count(User.id))).scalar()
    accounts = db.execute(select(func.count(Account.id))).scalar()
    open_alerts = db.execute(
        select(func.count(Alert.id)).where(Alert.status.in_(["open", "in_progress", "escalated"]))
    ).scalar()
    return {
        "users": users,
        "accounts": accounts,
        "transactions": txn_count,
        "flagged": flagged,
        "rejected": rejected,
        "open_alerts": open_alerts,
        "detection_rate": round(100 * (flagged + rejected) / txn_count, 2) if txn_count else 0.0,
    }


@router.get("/stats/risk-distribution")
def risk_distribution(db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    rows = db.execute(
        select(
            case(
                (Transaction.risk_score >= 80, "critical"),
                (Transaction.risk_score >= 50, "high"),
                (Transaction.risk_score >= 25, "medium"),
                else_="low",
            ).label("bucket"),
            func.count(Transaction.id),
        ).group_by("bucket")
    ).all()
    counts = {b: int(c) for b, c in rows}
    return {"buckets": ["low", "medium", "high", "critical"], "counts": counts}


@router.get("/stats/transaction-trend")
def transaction_trend(
    days: int = 14,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    start = datetime.now() - timedelta(days=days)
    rows = db.execute(
        select(
            func.date(Transaction.created_at).label("day"),
            func.count(Transaction.id),
        )
        .where(Transaction.created_at >= start)
        .group_by("day")
        .order_by("day")
    ).all()
    return {"labels": [str(day) for day, _ in rows], "values": [int(c) for _, c in rows]}


@router.get("/model-metrics")
def model_metrics(_: User = Depends(require_roles(UserRole.ADMIN))):
    info = runner.info
    if info is None:
        return {"available": False}
    return {
        "available": True,
        "version": info.get("version"),
        "trained_at": info.get("trained_at"),
        "metrics": info.get("metrics", {}),
        "threshold": info.get("threshold"),
    }


@router.get("/rules")
def list_rules(db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    return db.execute(select(Rule).order_by(Rule.code)).scalars().all()


@router.patch("/rules/{rule_id}")
def toggle_rule(
    rule_id: uuid.UUID,
    active: bool,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = active
    db.add(rule)
    record_audit(db, user, "rule.updated", "rule", str(rule.id), {"is_active": active})
    db.commit()
    db.refresh(rule)
    return rule