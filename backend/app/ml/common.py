"""Shared schema between ML training and runtime inference."""

FEATURE_COLUMNS = [
    "amount",
    "account_age_days",
    "txn_count_1h",
    "txn_count_24h",
    "failed_count_24h",
    "amount_sum_1h",
    "previous_amount",
    "avg_amount_30d",
    "amount_ratio",
    "distance_km",
    "speed_kmh",
    "hour_of_day",
    "is_weekend",
    "device_is_new",
    "location_is_new",
    "normal_hours",
    "unusual_frequency",
]

TX_TYPE_ONEHOT = ["txn_type_deposit", "txn_type_withdrawal", "txn_type_transfer", "txn_type_payment", "txn_type_refund"]

ALL_COLUMNS = FEATURE_COLUMNS + TX_TYPE_ONEHOT


def vector_from_features(features: dict) -> list[float]:
    """Order features into the numeric vector expected by the trained model."""
    vec = [float(features.get(c, 0.0) or 0.0) for c in FEATURE_COLUMNS]
    txn_type = features.get("transaction_type", "payment")
    for col in TX_TYPE_ONEHOT:
        vec.append(1.0 if col == f"txn_type_{txn_type}" else 0.0)
    return vec