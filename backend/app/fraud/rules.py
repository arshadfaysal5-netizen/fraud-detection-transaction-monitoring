"""Declarative rules for the fraud engine.

Each rule reads the feature set produced by app.fraud.features.build_features.
Default parameters mirror what the seeder writes to the `rules` table, so the
engine works even before seeding. The engine hard-evaluates high-risk observable
opportunities; every hit contributes weight toward the risk score.
"""

from __future__ import annotations

import logging

from app.models import Rule
from app.schemas import AlertSeverity

logger = logging.getLogger(__name__)

RuleResult = dict
RuleEvaluator = callable

DEFAULT_RULES: dict[str, dict] = {
    "high_frequency_velocity": {
        "name": "High-frequency velocity",
        "params": {"max_count_1h": 8, "max_count_24h": 20},
        "severity": AlertSeverity.MEDIUM,
        "weight": 15,
    },
    "amount_spike": {
        "name": "Unusual transaction amount",
        "params": {"max_ratio": 3.0},
        "severity": AlertSeverity.MEDIUM,
        "weight": 15,
    },
    "large_amount": {
        "name": "Large transaction amount",
        "params": {"max_amount": 10_000},
        "severity": AlertSeverity.MEDIUM,
        "weight": 12,
    },
    "geo_speed": {
        "name": "Impossible travel / geo-speed",
        "params": {"max_speed_kmh": 900},
        "severity": AlertSeverity.HIGH,
        "weight": 20,
    },
    "failed_attempts": {
        "name": "Multiple failed attempts",
        "params": {"max_failed_24h": 3},
        "severity": AlertSeverity.HIGH,
        "weight": 18,
    },
    "new_device": {
        "name": "Unusual device",
        "params": {"grace_new_days": 7},
        "severity": AlertSeverity.MEDIUM,
        "weight": 12,
    },
    "new_location": {
        "name": "Unusual location",
        "params": {"allow_radius_km": 250},
        "severity": AlertSeverity.MEDIUM,
        "weight": 12,
    },
    "odd_hours": {
        "name": "Off-hours transaction",
        "params": {"off_hours_start": 0, "off_hours_end": 5},
        "severity": AlertSeverity.LOW,
        "weight": 6,
    },
    "unusual_frequency": {
        "name": "Unusual transaction frequency",
        "params": {},
        "severity": AlertSeverity.HIGH,
        "weight": 16,
    },
}


def _evaluate_high_frequency(f: dict, p: dict) -> tuple[bool, str]:
    hit = f["txn_count_1h"] > p["max_count_1h"] or f["txn_count_24h"] > p["max_count_24h"]
    msg = (
        f"Rate of {f['txn_count_1h']}/1h, {f['txn_count_24h']}/24h exceeds "
        f"{p['max_count_1h']}/1h or {p['max_count_24h']}/24h"
    )
    return hit, msg


def _evaluate_amount_spike(f: dict, p: dict) -> tuple[bool, str]:
    ratio = f["amount_ratio"]
    if ratio is None or ratio <= p["max_ratio"]:
        return False, ""
    return True, f"Amount is {ratio:.1f}x the 30-day average ({p['max_ratio']}x allowed)"


def _evaluate_large_amount(f: dict, p: dict) -> tuple[bool, str]:
    hit = f["amount"] > p["max_amount"]
    return hit, f"Amount ${f['amount']:,.2f} exceeds ${p['max_amount']:,.2f}"


def _evaluate_geo_speed(f: dict, p: dict) -> tuple[bool, str]:
    hit = f["speed_kmh"] > p["max_speed_kmh"]
    return hit, f"Implied travel speed {f['speed_kmh']:.0f} km/h exceeds {p['max_speed_kmh']} km/h"


def _evaluate_failed_attempts(f: dict, p: dict) -> tuple[bool, str]:
    hit = f["failed_count_24h"] >= p["max_failed_24h"]
    return hit, f"{f['failed_count_24h']} failed attempts in the last 24h"


def _evaluate_new_device(f: dict, p: dict) -> tuple[bool, str]:
    hit = bool(f["device_is_new"])
    return hit, "Transaction initiated from a new/unseen device"


def _evaluate_new_location(f: dict, p: dict) -> tuple[bool, str]:
    hit = bool(f["location_is_new"])
    return hit, "Transaction initiated from an unfamiliar location"


def _evaluate_odd_hours(f: dict, p: dict) -> tuple[bool, str]:
    hour = f["hour_of_day"]
    hit = p["off_hours_start"] <= hour <= p["off_hours_end"]
    return hit, f"Transaction at {hour:02d}:00 (off-business-hours window)"


def _evaluate_unusual_frequency(f: dict, p: dict) -> tuple[bool, str]:
    hit = bool(f["unusual_frequency"])
    return hit, "Transaction stream shows unusual frequency strain pattern"


EVALUATORS: dict[str, RuleEvaluator] = {
    "high_frequency_velocity": _evaluate_high_frequency,
    "amount_spike": _evaluate_amount_spike,
    "large_amount": _evaluate_large_amount,
    "geo_speed": _evaluate_geo_speed,
    "failed_attempts": _evaluate_failed_attempts,
    "new_device": _evaluate_new_device,
    "new_location": _evaluate_new_location,
    "odd_hours": _evaluate_odd_hours,
    "unusual_frequency": _evaluate_unusual_frequency,
}


def _rule_configs(rule_rows: list[Rule]) -> list[dict]:
    registry = []
    for code, spec in DEFAULT_RULES.items():
        registry.append(
            {
                "code": code,
                "name": spec["name"],
                "params": spec["params"],
                "severity": spec["severity"],
                "weight": spec["weight"],
                "active": True,
            }
        )
    for row in rule_rows:
        idx = next((i for i, r in enumerate(registry) if r["code"] == row.code), None)
        entry = {
            "code": row.code,
            "name": row.name,
            "params": row.params or {},
            "severity": row.severity,
            "weight": row.weight,
            "active": row.is_active,
        }
        if idx is not None:
            registry[idx] = entry
        else:
            registry.append(entry)
    return registry


def evaluate_rules(features: dict, rule_rows: list[Rule]) -> list[dict]:
    hits = []
    for cfg in _rule_configs(rule_rows):
        evaluator = EVALUATORS.get(cfg["code"])
        if evaluator is None or not cfg["active"]:
            continue
        try:
            hit, message = evaluator(features, cfg["params"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Rule %s failed: %s", cfg["code"], exc)
            continue
        if hit:
            hits.append(
                {
                    "code": cfg["code"],
                    "name": cfg["name"],
                    "severity": cfg["severity"].value,
                    "weight": cfg["weight"],
                    "message": message,
                }
            )
    return hits


def rule_risk(hits: list[dict], base: float = 0.0) -> float:
    """Aggregate rule hits into a 0-100 contribution."""
    risk = base
    for hit in hits:
        _scaling = {"low": 1.0, "medium": 1.6, "high": 2.2, "critical": 3.0}
        risk += hit["weight"] * _scaling.get(hit["severity"], 1.0)
    return round(min(risk, 100.0), 1)