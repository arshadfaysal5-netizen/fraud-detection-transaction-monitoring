import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.kafka import publish_event
from app.core.redis_client import get_redis
from app.fraud.decision import decide
from app.fraud.features import (
    build_features,
    haversine_km,
    record_failed,
    record_transaction,
    velocity_amount_sum,
    velocity_count,
)
from app.fraud.ml import runner
from app.fraud.risk_score import combine_risk
from app.fraud.rules import evaluate_rules, rule_risk
from app.models import (
    Account,
    Device,
    MLScore,
    RiskProfile,
    Rule,
    Transaction,
    TxnFeature,
    User,
)
from app.schemas import AccountStatus, TxnStatus, TxnType, UserRole
from app.schemas.transaction import TxnCreate
from app.services.audit_service import record_audit


def _resolve_device(db: Session, user: User, req: TxnCreate) -> tuple[Device | None, bool]:
    """Return (device, is_new). Creates a device record on first sighting."""
    fp = (req.device_fingerprint or "").strip()
    if not fp:
        return None, False
    device = db.execute(select(Device).where(Device.fingerprint == fp)).scalar_one_or_none()
    if device is None:
        device = Device(
            user_id=user.id,
            fingerprint=fp,
            device_name=req.device_name or "",
            device_type=req.device_type or "",
            os=req.os or "",
        )
        db.add(device)
        db.flush()
        return device, True
    device.last_seen_at = datetime.now(timezone.utc)
    return device, False


def _is_familiar_location(db: Session, account: Account, lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return True
    recent = db.execute(
        select(Transaction.latitude, Transaction.longitude)
        .where(
            Transaction.account_id == account.id,
            Transaction.latitude.is_not(None),
            Transaction.longitude.is_not(None),
        )
        .order_by(Transaction.created_at.desc())
        .limit(10)
    ).all()
    for (k_lat, k_lon) in recent:
        if haversine_km(k_lat, k_lon, lat, lon) <= 250:
            return True
    return not recent  # no history yet → treat as familiar


def _publish_ingest(
    txn: Transaction, features: dict, ml_prob: float | None, model_version: str | None
) -> None:
    publish_event(
        "tx.ingest",
        "transaction.created",
        "transaction",
        str(txn.id),
        {
            "transaction_id": str(txn.id),
            "txn_ref": txn.txn_ref,
            "account_id": str(txn.account_id),
            "amount": float(txn.amount),
            "status": txn.status.value,
            "risk_score": txn.risk_score,
            "features": features,
            "ml_probability": ml_prob,
            "model_version": model_version,
        },
    )


def create_transaction(db: Session, user: User, req: TxnCreate, ip: str | None = None) -> Transaction:
    account = db.get(Account, req.account_id)
    if account is None:
        raise ValueError("Account not found")
    if account.user_id != user.id and user.role != UserRole.ADMIN:
        raise ValueError("Account does not belong to user")
    if account.status != AccountStatus.ACTIVE:
        raise ValueError("Account is not active")

    device, device_is_new = _resolve_device(db, user, req)
    location_is_new = not _is_familiar_location(db, account, req.latitude, req.longitude)

    redis = get_redis()
    features = build_features(
        db,
        redis,
        account,
        req.amount,
        req.txn_type.value,
        req.latitude,
        req.longitude,
        device_is_new=device_is_new,
        location_is_new=location_is_new,
    )

    rule_rows = db.execute(select(Rule)).scalars().all()
    rule_hits = evaluate_rules(features, rule_rows)
    r_risk = rule_risk(rule_hits)

    ml_prob = None
    ml_risk = None
    model_version = None
    if runner.available:
        try:
            ml_prob = runner.predict_proba(features)
            ml_risk = round(ml_prob * 100.0, 1)
            model_version = runner.version
        except Exception:  # noqa: BLE001
            ml_prob = None
            ml_risk = None

    risk = combine_risk(r_risk, ml_risk)
    status = decide(risk)

    reasons = [{"severity": h["severity"], "code": h["code"], "message": h["message"]} for h in rule_hits]

    # Check available balance for debits
    debit_types = {TxnType.WITHDRAWAL, TxnType.TRANSFER, TxnType.PAYMENT}
    if req.txn_type in debit_types and status == TxnStatus.APPROVED:
        if Decimal(str(account.balance or 0)) < Decimal(str(req.amount)):
            status = TxnStatus.REJECTED
            reasons.append({"severity": "medium", "code": "insufficient_funds", "message": "Insufficient account balance"})

    txn = Transaction(
        txn_ref=str(uuid.uuid4()),
        account_id=account.id,
        txn_type=req.txn_type,
        amount=req.amount,
        currency=req.currency,
        status=status,
        risk_score=risk,
        decision_reason=reasons,
        channel=req.channel,
        device_id=device.id if device else None,
        latitude=req.latitude,
        longitude=req.longitude,
        city=req.city,
        country=req.country,
        ip_address=req.ip_address or ip,
        extra_data=req.metadata or {},
        processed_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    db.flush()

    db.add(
        TxnFeature(
            transaction_id=txn.id,
            amount=features["amount"],
            transaction_type=features["transaction_type"],
            account_age_days=features["account_age_days"],
            txn_count_1h=features["txn_count_1h"],
            txn_count_24h=features["txn_count_24h"],
            failed_count_24h=features["failed_count_24h"],
            amount_sum_1h=features["amount_sum_1h"],
            previous_amount=features["previous_amount"],
            avg_amount_30d=features["avg_amount_30d"],
            amount_ratio=features["amount_ratio"],
            distance_km=features["distance_km"],
            speed_kmh=features["speed_kmh"],
            hour_of_day=features["hour_of_day"],
            is_weekend=features["is_weekend"],
            device_is_new=features["device_is_new"],
            location_is_new=features["location_is_new"],
            normal_hours=features["normal_hours"],
        )
    )

    if ml_prob is not None:
        from app.ml.common import ALL_COLUMNS

        db.add(
            MLScore(
                transaction_id=txn.id,
                model_version=model_version or "unknown",
                fraud_probability=ml_prob,
                ml_risk=ml_risk or 0.0,
                shap_json=runner.explain(features) or {},
            )
        )

    if status == TxnStatus.APPROVED:
        current = Decimal(str(account.balance or 0))
        sign = Decimal("1") if req.txn_type in {TxnType.DEPOSIT, TxnType.REFUND} else Decimal("-1")
        account.balance = float(current + sign * Decimal(str(req.amount)))
    elif status == TxnStatus.REJECTED:
        record_failed(redis, str(account.id))
        _bump_risk_profile(db, account.user_id, failed=True)

    record_transaction(redis, str(account.id), req.amount)
    _bump_risk_profile(db, account.user_id, risk_score=risk, flagged=(status == TxnStatus.FLAGGED))

    db.flush()
    if status == TxnStatus.FLAGGED or (status == TxnStatus.REJECTED and rule_hits):
        from app.services.alert_service import create_alerts_for_transaction

        create_alerts_for_transaction(db, txn, rule_hits)
    record_audit(
        db, user, "transaction.created", "transaction", str(txn.id),
        {"txn_ref": txn.txn_ref, "status": status.value, "risk_score": risk},
        ip_address=req.ip_address or ip,
    )
    db.commit()
    db.refresh(txn)

    _publish_ingest(txn, features, ml_prob, model_version)
    return txn


def _bump_risk_profile(
    db: Session, user_id: uuid.UUID, risk_score: int = 0, failed: bool = False, flagged: bool = False
) -> RiskProfile:
    profile = db.execute(select(RiskProfile).where(RiskProfile.user_id == user_id)).scalar_one_or_none()
    if profile is None:
        profile = RiskProfile(user_id=user_id)
        db.add(profile)
    profile.risk_score_current = max(profile.risk_score_current, risk_score)
    if failed:
        profile.failed_attempts_24h = (profile.failed_attempts_24h or 0) + 1
    if flagged:
        profile.flagged_count_30d = (profile.flagged_count_30d or 0) + 1
    profile.last_event_at = datetime.now(timezone.utc)
    if profile.risk_score_current >= 80:
        profile.risk_level = "high"
    elif profile.risk_score_current >= 50:
        profile.risk_level = "medium"
    return profile


def review_transaction(db: Session, user: User, txn_id: uuid.UUID, decision: str, reason: str) -> dict:
    """Analyst manually overrides a transaction decision (investigation action)."""
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise ValueError("Transaction not found")

    new_status = {
        "approved": TxnStatus.APPROVED,
        "rejected": TxnStatus.REJECTED,
        "flagged": TxnStatus.FLAGGED,
    }[decision]

    txn.status = new_status
    reasons = list(txn.decision_reason or [])
    reasons.append(
        {
            "severity": "info",
            "code": "manual_override",
            "message": f"{decision.upper()} by {user.username} — {reason}",
        }
    )
    txn.decision_reason = reasons
    txn.processed_at = datetime.now(timezone.utc)
    db.add(txn)
    record_audit(
        db, user, "transaction.review", "transaction", str(txn.id),
        {"decision": decision, "reason": reason},
    )
    db.commit()
    db.refresh(txn)
    return {"status": new_status.value, "transaction": txn}