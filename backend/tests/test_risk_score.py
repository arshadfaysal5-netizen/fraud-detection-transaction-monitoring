from app.fraud.risk_score import combine_risk, risk_level


def test_ml_only():
    assert combine_risk(0.0, 100.0) == 55  # 0.45*0 + 0.55*100


def test_rule_only():
    assert combine_risk(80.0, None) == 80  # no model -> rule risk alone


def test_clamping():
    assert combine_risk(100.0, 100.0) <= 100
    assert combine_risk(0.0, 0.0) == 0


def test_risk_level_labels():
    assert risk_level(90) == "critical"
    assert risk_level(60) == "high"
    assert risk_level(30) == "medium"
    assert risk_level(10) == "low"