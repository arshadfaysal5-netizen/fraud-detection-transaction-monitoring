"""Feature computation for the fraud engine.

Velocity counters and recent-transaction windows live in Redis (fast, TTL-backed).
Longer-horizon stats (30-day averages, account age) come from PostgreSQL.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Transaction


def _key(account_id: str, suffix: str) -> str:
    return f"tx:{account_id}:{suffix}"


def _client(r):
    return getattr(r, "client", r)


def velocity_count(r, account_id: str, window_seconds: int) -> int:
    c = _client(r)
    if hasattr(c, "get"):
        return int(c.get(_key(account_id, f"count:{window_seconds}s")) or 0)
    return 0


def velocity_amount_sum(r, account_id: str, window_seconds: int) -> float:
    c = _client(r)
    if hasattr(c, "get"):
        return float(c.get(_key(account_id, f"amount:{window_seconds}s")) or 0)
    return 0.0


def failed_count(r, account_id: str, window_seconds: int = 86_400) -> int:
    c = _client(r)
    if hasattr(c, "get"):
        return int(c.get(_key(account_id, f"failed:{window_seconds}s")) or 0)
    return 0


def recent_amounts(r, account_id: str, n: int = 5) -> list[float]:
    c = _client(r)
    if hasattr(c, "lrange"):
        raw = c.lrange(_key(account_id, "recent"), 0, n - 1)
        return [float(v) for v in raw]
    return []


def record_transaction(r, account_id: str, amount: float) -> None:
    """Update velocity counters after a transaction attempt."""
    c = _client(r)
    if hasattr(c, "incr"):
        c.incr(_key(account_id, "count:3600s"), ttl=3600)
        c.incr(_key(account_id, "count:86400s"), ttl=86_400)
        c.incrbyfloat(_key(account_id, "amount:3600s"), float(amount), ttl=3600)
        c.lpush(_key(account_id, "recent"), f"{amount:.2f}")


def record_failed(r, account_id: str) -> None:
    c = _client(r)
    if hasattr(c, "incr"):
        c.incr(_key(account_id, "failed:86400s"), ttl=86_400)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    if None in (lat1, lon1, lat2, lon2):
        return 0.0
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def avg_amount_30d(db: Session, account_id: uuid.UUID) -> float | None:
    value = db.execute(
        select(func.avg(Transaction.amount)).where(Transaction.account_id == account_id)
    ).scalar()
    return float(value) if value is not None else None


def prev_txn_summary(
    db: Session, account_id: uuid.UUID
) -> tuple[float | None, float | None, float | None, float | None]:
    """Return (previous_amount, prev_lat, prev_lon, prev_epoch_time)."""
    txn = (
        db.execute(
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if txn is None:
        return None, None, None, None
    return (
        float(txn.amount),
        txn.latitude,
        txn.longitude,
        txn.created_at.timestamp() if txn.created_at else None,
    )


def build_features(
    db: Session,
    r,
    account: Account,
    amount: float,
    txn_type: str,
    latitude: float | None,
    longitude: float | None,
    device_is_new: bool,
    location_is_new: bool,
) -> dict:
    """Assemble the full feature set used by the rules engine and ML model."""
    now = datetime.now(timezone.utc)

    prev_amount, prev_lat, prev_lon, prev_ts = prev_txn_summary(db, account.id)

    count_1h = velocity_count(r, str(account.id), 3600)
    count_24h = velocity_count(r, str(account.id), 86_400)
    amount_1h = velocity_amount_sum(r, str(account.id), 3600)
    fails_24h = failed_count(r, str(account.id))

    avg30 = avg_amount_30d(db, account.id)
    amount_ratio = (amount / avg30) if avg30 else None

    distance = haversine_km(prev_lat, prev_lon, latitude, longitude) if prev_lat and latitude else 0.0
    speed = 0.0
    if prev_ts and distance:
        dt_hours = max((now.timestamp() - prev_ts) / 3600.0, 1 / 3600)
        speed = distance / dt_hours

    hour = now.hour
    is_weekend = now.weekday() >= 5
    normal_hours = 6 <= hour < 23

    return {
        "amount": float(amount),
        "transaction_type": txn_type,
        "account_age_days": account.account_age_days,
        "txn_count_1h": count_1h,
        "txn_count_24h": count_24h,
        "failed_count_24h": fails_24h,
        "amount_sum_1h": amount_1h,
        "previous_amount": prev_amount,
        "avg_amount_30d": avg30,
        "amount_ratio": amount_ratio,
        "distance_km": round(distance, 2),
        "speed_kmh": round(speed, 1),
        "hour_of_day": hour,
        "is_weekend": is_weekend,
        "normal_hours": normal_hours,
        "device_is_new": device_is_new,
        "location_is_new": location_is_new,
        "unusual_frequency": count_1h > 5 and count_24h > 15,
    }