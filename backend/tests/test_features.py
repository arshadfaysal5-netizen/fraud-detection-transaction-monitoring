from app.core.redis_client import LocalTTLCache
from app.fraud.features import (
    failed_count,
    haversine_km,
    record_failed,
    record_transaction,
    recent_amounts,
    velocity_amount_sum,
    velocity_count,
)


def test_velocity_counters_with_fallback():
    cache = LocalTTLCache()
    record_transaction(cache, "acct-1", 100.5)
    record_transaction(cache, "acct-1", 250.0)
    assert velocity_count(cache, "acct-1", 3600) == 2
    assert velocity_amount_sum(cache, "acct-1", 3600) == 350.5
    assert recent_amounts(cache, "acct-1", 2) == [250.0, 100.5]


def test_failed_counter():
    cache = LocalTTLCache()
    for _ in range(3):
        record_failed(cache, "acct-1")
    assert failed_count(cache, "acct-1") == 3


def test_haversine_far_distance():
    nyc = (40.7128, -74.0060)
    tokyo = (35.6762, 139.6503)
    km = haversine_km(*nyc, *tokyo)
    assert 10_000 < km < 12_000


def test_haversine_zero_for_missing():
    assert haversine_km(None, None, 1.0, 2.0) == 0.0