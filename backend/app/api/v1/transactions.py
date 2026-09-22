import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import account_belongs_to, get_current_user, require_roles
from app.core.db import get_db
from app.models import Account, Transaction, User
from app.schemas import TxnStatus, TxnType, UserRole
from app.schemas.transaction import (
    TxnCreate,
    TxnDecision,
    TxnOut,
    TxnReviewOut,
    TxnReviewRequest,
)
from app.services.transaction_service import create_transaction, review_transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _visible_accounts(db: Session, user: User) -> list[uuid.UUID]:
    if user.role in (UserRole.ADMIN, UserRole.ANALYST):
        return [a.id for a in db.execute(select(Account)).scalars()]
    return [a.id for a in db.execute(select(Account).where(Account.user_id == user.id)).scalars()]


@router.post("", response_model=TxnDecision, status_code=201,
             summary="Submit a transaction (real-time risk scoring)")
def submit_transaction(
    req: TxnCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        txn = create_transaction(db, user, req, ip=request.client.host if request.client else None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    ml_prob = txn.ml_score.fraud_probability if txn.ml_score else None
    return TxnDecision(
        transaction=TxnOut.model_validate(txn),
        risk_score=txn.risk_score or 0,
        status=txn.status,
        decision_reasons=txn.decision_reason or [],
        ml_probability=ml_prob,
    )


@router.get("", response_model=list[TxnOut])
def list_transactions(
    account_id: uuid.UUID | None = None,
    status: TxnStatus | None = None,
    txn_type: TxnType | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Transaction)
    if account_id:
        query = query.where(Transaction.account_id == account_id)
    elif user.role not in (UserRole.ADMIN, UserRole.ANALYST):
        ids = _visible_accounts(db, user)
        query = query.where(Transaction.account_id.in_(ids)) if ids else query.where(False)
    if status:
        query = query.where(Transaction.status == status)
    if txn_type:
        query = query.where(Transaction.txn_type == txn_type)
    if from_date:
        query = query.where(Transaction.created_at >= from_date)
    if to_date:
        query = query.where(Transaction.created_at <= to_date)
    rows = db.execute(query.order_by(Transaction.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return rows


@router.get("/{txn_id}", response_model=TxnOut)
def get_transaction(
    txn_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if user.role not in (UserRole.ADMIN, UserRole.ANALYST) and str(txn.account_id) not in _visible_accounts(db, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    return txn


@router.post("/{txn_id}/review", response_model=TxnReviewOut)
def review(
    txn_id: uuid.UUID,
    req: TxnReviewRequest,
    user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        result = review_transaction(db, user, txn_id, req.decision, req.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return TxnReviewOut(transaction=TxnOut.model_validate(result["transaction"]), status=result["status"])


@router.get("/stats/summary")
def transaction_stats(
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    now = datetime.now()
    day_ago = now - timedelta(hours=24)
    total = db.execute(select(func.count(Transaction.id))).scalar()
    flagged = db.execute(
        select(func.count(Transaction.id)).where(Transaction.status == TxnStatus.FLAGGED)
    ).scalar()
    rejected = db.execute(
        select(func.count(Transaction.id)).where(Transaction.status == TxnStatus.REJECTED)
    ).scalar()
    approved = db.execute(
        select(func.count(Transaction.id)).where(Transaction.status == TxnStatus.APPROVED)
    ).scalar()
    last24h = db.execute(
        select(func.count(Transaction.id)).where(Transaction.created_at >= day_ago)
    ).scalar()
    return {
        "total": total,
        "approved": approved,
        "flagged": flagged,
        "rejected": rejected,
        "last_24h": last24h,
        "detection_rate": round(100 * (flagged + rejected) / total, 2) if total else 0.0,
    }