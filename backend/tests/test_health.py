def test_health():
    from app.main import app

    assert app.title.startswith("Fraud Detection")
    assert app.version == "1.0.0"