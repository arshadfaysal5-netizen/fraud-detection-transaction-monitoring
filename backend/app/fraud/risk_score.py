"""Fusion of rule-based risk and ML risk into a single 0-100 score."""

from app.core.config import settings


def combine_risk(rule_risk: float, ml_risk: float | None) -> int:
    """Weighted fusion.

    When the ML component is absent (no trained model) the rule risk is used
    as-is so scoring remains meaningful without sacrificing accuracy.
    """
    if ml_risk is None:
        return int(round(rule_risk))
    fused = settings.risk_weight_rule * rule_risk + settings.risk_weight_ml * ml_risk
    return int(round(min(max(fused, 0.0), 100.0)))


def risk_level(risk_score: int) -> str:
    if risk_score >= settings.risk_threshold_block:
        return "critical"
    if risk_score >= settings.risk_threshold_review:
        return "high"
    if risk_score >= 25:
        return "medium"
    return "low"