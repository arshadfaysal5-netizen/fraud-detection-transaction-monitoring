from app.fraud.rules import evaluate_rules, rule_risk
from app.schemas import AlertSeverity


def test_high_frequency_rule_hits():
    features = {
        "txn_count_1h": 12,
        "txn_count_24h": 30,
        "amount_ratio": 1.1,
        "amount": 100,
        "speed_kmh": 5,
        "failed_count_24h": 0,
        "device_is_new": False,
        "location_is_new": False,
        "hour_of_day": 12,
        "unusual_frequency": True,
        "normal_hours": True,
    }
    hits = evaluate_rules(features, [])
    codes = {h["code"] for h in hits}
    assert "high_frequency_velocity" in codes
    assert "unusual_frequency" in codes
    assert "amount_spike" not in codes


def test_amount_spike_and_geo():
    features = {
        "txn_count_1h": 1,
        "txn_count_24h": 5,
        "amount_ratio": 8.0,
        "amount": 500,
        "speed_kmh": 3000,
        "failed_count_24h": 0,
        "device_is_new": False,
        "location_is_new": False,
        "hour_of_day": 14,
        "unusual_frequency": False,
        "normal_hours": True,
    }
    hits = evaluate_rules(features, [])
    codes = {h["code"] for h in hits}
    assert "amount_spike" in codes
    assert "geo_speed" in codes


def test_rule_risk_scales_by_severity():
    assert rule_risk([]) == 0
    low = rule_risk([{"severity": "low", "weight": 10}])
    high = rule_risk([{"severity": "high", "weight": 10}])
    assert high > low
    assert rule_risk([{"severity": "critical", "weight": 50}]) == 100  # capped


def test_inactive_rules_ignored():
    features = {
        "txn_count_1h": 12,
        "txn_count_24h": 30,
        "amount_ratio": 1.0,
        "amount": 100,
        "speed_kmh": 1,
        "failed_count_24h": 0,
        "device_is_new": False,
        "location_is_new": False,
        "hour_of_day": 12,
        "unusual_frequency": False,
        "normal_hours": True,
    }
    fake_rule = type("Rule", (), {"code": "high_frequency_velocity", "name": "HF", "params": {}, "severity": AlertSeverity.MEDIUM, "weight": 15, "is_active": False})
    hits = evaluate_rules(features, [fake_rule])
    assert not any(h["code"] == "high_frequency_velocity" for h in hits)