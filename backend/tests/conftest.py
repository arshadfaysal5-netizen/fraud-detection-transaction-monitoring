"""Test configuration: run against SQLite in-memory and no external services."""

import os
import tempfile
import uuid

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_tmp_db.name}"
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6399/0")
os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9093")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal, init_db
from app.main import app


def unique_email() -> str:
    return f"user_{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture(scope="session", autouse=True)
def _database():
    init_db()
    yield
    SessionLocal().close()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def registered_user(client: TestClient) -> dict:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email(),
            "username": f"cust_{uuid.uuid4().hex[:8]}",
            "full_name": "Test Customer",
            "password": "password123",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture()
def customer_token(registered_user) -> str:
    return registered_user["access_token"]


@pytest.fixture()
def admin_token() -> str:
    from app.core.security import create_access_token, hash_password
    from app.models import RiskProfile, User
    from app.models.enums import UserRole

    sess = SessionLocal()
    try:
        user = User(
            email=unique_email(),
            username=f"admin_{uuid.uuid4().hex[:8]}",
            full_name="Test Admin",
            password_hash=hash_password("password123"),
            role=UserRole.ADMIN,
        )
        sess.add(user)
        sess.flush()
        sess.add(RiskProfile(user_id=user.id))
        sess.commit()
        return create_access_token(str(user.id), user.role.value)
    finally:
        sess.close()