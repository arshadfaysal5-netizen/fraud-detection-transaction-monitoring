import uuid

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.ml.common import ALL_COLUMNS, vector_from_features


def test_password_hash_roundtrip():
    h = hash_password("password123")
    assert h != "password123"
    assert verify_password("password123", h)
    assert not verify_password("wrong", h)
    assert not verify_password("password123", "garbage")


def test_token_roundtrip():
    token = create_access_token(str(uuid.uuid4()), "customer")
    payload = decode_token(token)
    assert payload["type"] == "access"
    with pytest.raises(Exception):
        decode_token(token + "tampered")


def test_refresh_token_type():
    token = create_refresh_token("uid", "admin")
    assert decode_token(token)["type"] == "refresh"


def test_feature_vector_shape():
    features = {
        "amount": 100,
        "account_age_days": 30,
        "txn_count_1h": 2,
        "txn_count_24h": 10,
        "failed_count_24h": 0,
        "amount_sum_1h": 200,
        "previous_amount": 50,
        "avg_amount_30d": 150,
        "amount_ratio": 0.67,
        "distance_km": 5,
        "speed_kmh": 20,
        "hour_of_day": 12,
        "is_weekend": False,
        "device_is_new": False,
        "location_is_new": False,
        "normal_hours": True,
        "unusual_frequency": False,
        "transaction_type": "payment",
    }
    vec = vector_from_features(features)
    assert len(vec) == len(ALL_COLUMNS)
    assert vec[ALL_COLUMNS.index("amount")] == 100.0
    assert vec[ALL_COLUMNS.index("txn_type_payment")] == 1.0
    assert vec[ALL_COLUMNS.index("txn_type_withdrawal")] == 0.0