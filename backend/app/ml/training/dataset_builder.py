"""Dataset builder: labels from real monitored transactions, with a synthetic
fallback generator so the pipeline trains even before rich real data exists.

Ground-truth label rule (aligns with the fraud engine):
    flagged or rejected transaction  -> fraud = 1
    approved transaction             -> fraud = 0
"""

from __future__ import annotations

import random

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.common import FEATURE_COLUMNS, vector_from_features
from app.models import TxnFeature, Transaction
from app.schemas import TxnStatus

FRAUD_PATTERNS = range(1, 7)
TX_TYPES = ["deposit", "withdrawal", "transfer", "payment", "refund"]


def _synth_txn() -> dict:
    """Generate one realistic/suspicious feature vector."""
    pattern = random.choice(list(FRAUD_PATTERNS)) if random.random() < 0.5 else 0

    amount = round(random.uniform(5, 2000), 2)
    count_1h = random.randint(1, 4)
    count_24h = random.randint(1, 15)
    fails_24h = random.randint(0, 2)
    speed = random.uniform(0, 200)
    hour = random.randint(8, 22)
    acc_age = random.randint(30, 1200)
    prev_amount = round(random.uniform(5, 2000), 2)
    avg = round(random.uniform(5, 2000), 2)
    ratio = amount / avg
    distance = random.uniform(0, 30)
    is_weekend = random.random() < 0.29
    new_device = False
    new_location = False
    normal_hours = True

    label = 0
    # Fraud injection patterns
    if pattern == 1:  # amount spike
        amount, ratio, label = round(avg * random.uniform(4, 12), 2), 4 + random.random() * 8, 1
    elif pattern == 2:  # high velocity
        count_1h, count_24h, label = random.randint(9, 20), random.randint(21, 60), 1
    elif pattern == 3:  # impossible travel
        distance, speed, hour, label = 12000, random.uniform(1200, 5000), random.randint(0, 4), 1
    elif pattern == 4:  # failed attempts + new device
        fails_24h, new_device, label = random.randint(4, 8), True, 1
    elif pattern == 5:  # odd hours + new location
        hour, new_location, label = random.randint(0, 4), True, 1
    elif pattern == 6:  # abnormal amount on new account
        account_age_days = random.randint(1, 10)
        amount, ratio, label = round(avg * random.uniform(5, 15), 2), 5 + random.random() * 10, 1
        return {
            "amount": amount,
            "transaction_type": random.choice(TX_TYPES),
            "account_age_days": account_age_days,
            "txn_count_1h": count_1h,
            "txn_count_24h": count_24h,
            "failed_count_24h": fails_24h,
            "amount_sum_1h": amount,
            "previous_amount": prev_amount,
            "avg_amount_30d": avg,
            "amount_ratio": ratio,
            "distance_km": distance,
            "speed_kmh": speed,
            "hour_of_day": hour,
            "is_weekend": is_weekend,
            "device_is_new": new_device,
            "location_is_new": new_location,
            "normal_hours": normal_hours,
            "unusual_frequency": count_1h > 5 and count_24h > 15,
            "label": label,
        }

    return {
        "amount": amount,
        "transaction_type": random.choice(TX_TYPES),
        "account_age_days": acc_age,
        "txn_count_1h": count_1h,
        "txn_count_24h": count_24h,
        "failed_count_24h": fails_24h,
        "amount_sum_1h": round(count_1h * amount, 2),
        "previous_amount": prev_amount,
        "avg_amount_30d": avg,
        "amount_ratio": round(ratio, 3),
        "distance_km": round(distance, 2),
        "speed_kmh": round(speed, 1),
        "hour_of_day": hour,
        "is_weekend": is_weekend,
        "device_is_new": new_device,
        "location_is_new": new_location,
        "normal_hours": normal_hours,
        "unusual_frequency": count_1h > 5 and count_24h > 15,
        "label": label,
    }


def build_synthetic(n: int = 10_000, seed: int = 42) -> dict:
    """Return numpy arrays of features + labels (synthetic, labeled)."""
    random.seed(seed)
    rows = [_synth_txn() for _ in range(n)]
    features = [
        vector_from_features({k: v for k, v in r.items() if k != "label"}) for r in rows
    ]
    labels = [r["label"] for r in rows]
    return {
        "X": np.array(features, dtype=float),
        "y": np.array(labels, dtype=int),
        "columns": FEATURE_COLUMNS,
    }


def build_from_db(db: Session, limit: int = 100_000) -> dict | None:
    """Assemble labeled vectors from monitored transactions (may be None when empty)."""
    rows = db.execute(
        select(TxnFeature, Transaction.status)
        .join(Transaction, TxnFeature.transaction_id == Transaction.id)
        .limit(limit)
    ).all()
    if not rows:
        return None

    features, labels = [], []
    fraud_statuses = {TxnStatus.FLAGGED, TxnStatus.REJECTED}
    for feat, status in rows:
        feature_dict = {
            "amount": feat.amount,
            "transaction_type": feat.transaction_type,
            "account_age_days": feat.account_age_days,
            "txn_count_1h": feat.txn_count_1h,
            "txn_count_24h": feat.txn_count_24h,
            "failed_count_24h": feat.failed_count_24h,
            "amount_sum_1h": feat.amount_sum_1h,
            "previous_amount": feat.previous_amount,
            "avg_amount_30d": feat.avg_amount_30d,
            "amount_ratio": feat.amount_ratio,
            "distance_km": feat.distance_km,
            "speed_kmh": feat.speed_kmh,
            "hour_of_day": feat.hour_of_day,
            "is_weekend": bool(feat.is_weekend),
            "device_is_new": bool(feat.device_is_new),
            "location_is_new": bool(feat.location_is_new),
            "normal_hours": bool(feat.normal_hours),
            "unusual_frequency": feat.txn_count_1h > 5 and feat.txn_count_24h > 15,
        }
        features.append(vector_from_features(feature_dict))
        labels.append(1 if status in fraud_statuses else 0)

    return {
        "X": np.array(features, dtype=float),
        "y": np.array(labels, dtype=int),
        "columns": FEATURE_COLUMNS,
    }