import uuid

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models import Alert


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health(client: TestClient):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_register_and_login(client: TestClient):
    username = f"u_{uuid.uuid4().hex[:8]}"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{username}@example.com",
            "username": username,
            "full_name": "Test",
            "password": "password123",
        },
    )
    assert reg.status_code == 201, reg.text
    assert reg.json()["access_token"]

    login = client.post("/api/v1/auth/login", json={"username": username, "password": "password123"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "customer"

    bad = client.post("/api/v1/auth/login", json={"username": username, "password": "nope"})
    assert bad.status_code == 401


def test_create_account_and_list(client: TestClient, customer_token):
    res = client.post(
        "/api/v1/accounts",
        json={"account_type": "checking", "opening_balance": 500},
        headers=_auth_headers(customer_token),
    )
    assert res.status_code == 201, res.text
    account = res.json()
    assert account["balance"] == 500.00

    listing = client.get("/api/v1/accounts", headers=_auth_headers(customer_token))
    assert listing.status_code == 200
    assert any(a["id"] == account["id"] for a in listing.json())


def test_suspicious_transaction_is_flagged_and_alerts(client: TestClient, customer_token):
    account = client.post(
        "/api/v1/accounts",
        json={"account_type": "checking", "opening_balance": 200},
        headers=_auth_headers(customer_token),
    ).json()
    acct_id = account["id"]

    # Repeated high-value withdrawals exceeding the balance burn through the
    # failed-attempt counter until the failed_attempts rule trips.
    last_status = None
    for _ in range(4):
        res = client.post(
            "/api/v1/transactions",
            json={
                "account_id": acct_id,
                "txn_type": "withdrawal",
                "amount": 15_000,
                "channel": "web",
                "device_fingerprint": "device-attacker-1",
                "latitude": 35.6762,
                "longitude": 139.6503,
                "city": "Tokyo",
                "country": "JP",
            },
            headers=_auth_headers(customer_token),
        )
        assert res.status_code == 201, res.text
        last_status = res.json()["status"]
        if res.json()["status"] != "approved":
            last_risk = res.json()["risk_score"]

    assert last_status == "flagged", "expected a flagged decision after failed attempts"

    # alerts should exist (summary + per-rule)
    admin = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"admin_{uuid.uuid4().hex[:8]}@example.com",
            "username": f"analyst_{uuid.uuid4().hex[:8]}",
            "full_name": "Analyst",
            "password": "password123",
        },
    )
    admin_token = admin.json()["access_token"]

    # promote registered user to analyst via DB
    sess = SessionLocal()
    from app.models import User
    from app.models.enums import UserRole

    from app.core.security import decode_token

    found = sess.query(User).filter(User.id == uuid.UUID(decode_token(admin_token)["sub"])).one()
    found.role = UserRole.ANALYST
    sess.commit()
    sess.close()

    alerts = client.get(
        "/api/v1/alerts",
        headers=_auth_headers(admin_token),
    )
    assert alerts.status_code == 200
    assert any(a["risk_score"] >= 50 for a in alerts.json())


def test_unauthorized_access_rejected(client: TestClient, customer_token):
    res = client.get("/api/v1/admin/stats/overview", headers=_auth_headers(customer_token))
    assert res.status_code == 403