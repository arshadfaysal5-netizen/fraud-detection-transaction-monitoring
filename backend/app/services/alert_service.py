import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.kafka import publish_event
from app.models import Account, Alert, Transaction, User
from app.schemas import AlertSeverity, AlertStatus, TxnStatus
from app.services.audit_service import record_audit


def _severity_for(risk: int, rule_hits: list) -> AlertSeverity:
    worst = max((h.get("severity", "low") for h in rule_hits), default="low")
    order = ["low", "medium", "high", "critical"]
    if risk >= 80:
        return AlertSeverity.CRITICAL
    if risk >= 50 or worst in ("high", "critical"):
        return AlertSeverity.HIGH
    if worst == "medium":
        return AlertSeverity.MEDIUM
    return AlertSeverity.LOW


def create_alerts_for_transaction(db: Session, txn: Transaction, rule_hits: list) -> list[Alert]:
    """Raise alerts for flagged/rejected transactions.

    Rule hits drive one alert per high/critical rule plus a single summary alert
    for the transaction's overall risk. Called synchronously so alerts exist even
    when the async Kafka worker is unavailable; the worker re-publishes them.
    """
    if txn.status not in (TxnStatus.FLAGGED, TxnStatus.REJECTED):
        return []

    account = db.get(Account, txn.account_id)
    alerts: list[Alert] = []

    serious = [h for h in rule_hits if h.get("severity") in ("high", "critical")]
    summary_alert = Alert(
        ref_no=_new_ref_no(),
        account_id=txn.account_id,
        user_id=account.user_id if account else None,
        transaction_id=txn.id,
        severity=_severity_for(txn.risk_score or 0, rule_hits),
        status=AlertStatus.OPEN,
        alert_type="risk_score",
        rule_code=None,
        risk_score=txn.risk_score or 0,
        description=_describe(txn, rule_hits),
    )
    alerts.append(summary_alert)
    db.add(summary_alert)

    for hit in serious:
        alert = Alert(
            ref_no=_new_ref_no(),
            account_id=txn.account_id,
            user_id=account.user_id if account else None,
            transaction_id=txn.id,
            severity=AlertSeverity(hit["severity"]),
            status=AlertStatus.OPEN,
            alert_type=f"rule:{hit['code']}",
            rule_code=hit["code"],
            risk_score=txn.risk_score or 0,
            description=hit["message"],
        )
        alerts.append(alert)
        db.add(alert)

    db.flush()
    db.commit()
    for alert in alerts:
        publish_event(
            "alerts",
            "alert.created",
            "alert",
            str(alert.id),
            {"ref_no": alert.ref_no, "severity": alert.severity.value, "risk_score": alert.risk_score},
        )
        from app.core.events import hub

        hub.publish(
            {
                "type": "alert",
                "alert_id": str(alert.id),
                "ref_no": alert.ref_no,
                "account_id": str(alert.account_id),
                "severity": alert.severity.value,
                "status": alert.status.value,
                "risk_score": alert.risk_score,
                "alert_type": alert.alert_type,
                "description": alert.description,
            }
        )
    return alerts


def _describe(txn: Transaction, rule_hits: list) -> str:
    reasons = ", ".join(h["code"] for h in rule_hits) or "model-based risk"
    return (
        f"{txn.txn_type.value.title()} of ${float(txn.amount):,.2f} on account "
        f"{str(txn.account_id)[:8]} flagged at risk {txn.risk_score}/100. Signals: {reasons}."
    )


def _new_ref_no() -> str:
    return f"ALT-{secrets.token_hex(3).upper()}"


def list_alerts(db: Session, status: AlertStatus | None, severity: AlertSeverity | None, limit: int, offset: int):
    query = select(Alert)
    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
    return db.execute(query.order_by(Alert.created_at.desc()).limit(limit).offset(offset)).scalars().all()


def update_alert(db: Session, user: User, alert: Alert, new_status: AlertStatus, reason: str | None) -> Alert:
    if new_status in (AlertStatus.RESOLVED, AlertStatus.FALSE_POSITIVE):
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolution_reason = reason
    alert.status = new_status
    db.add(alert)
    record_audit(
        db, user, "alert.updated", "alert", str(alert.id),
        {"status": new_status.value, "reason": reason},
    )
    db.commit()
    db.refresh(alert)
    return alert


def get_risk_profile(db: Session, user_id: uuid.UUID):
    from app.models import RiskProfile

    return db.execute(select(RiskProfile).where(RiskProfile.user_id == user_id)).scalar_one_or_none()