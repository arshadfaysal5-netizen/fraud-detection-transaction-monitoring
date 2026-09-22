"""Seed default rules and demo users/accounts for local development."""

import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.db import SessionLocal, init_db
from app.core.security import hash_password
from app.fraud.rules import DEFAULT_RULES
from app.models import Account, RiskProfile, Rule, User
from app.schemas import AccountType, UserRole


def seed_rules(db) -> None:
    existing = {r.code for r in db.execute(select(Rule)).scalars()}
    for code, spec in DEFAULT_RULES.items():
        if code in existing:
            continue
        db.add(
            Rule(
                code=code,
                name=spec["name"],
                description=spec["name"],
                params=spec["params"],
                severity=spec["severity"],
                weight=spec["weight"],
            )
        )
    db.commit()
    print(f"Seeded {len(DEFAULT_RULES)} fraud rules")


def _ensure_user(db, username: str, email: str, full_name: str, role: UserRole, password: str = "password123") -> User:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user:
        return user
    user = User(
        email=email,
        username=username,
        full_name=full_name,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.flush()
    db.add(RiskProfile(user_id=user.id))
    return user


def seed_users_and_accounts(db) -> None:
    seed = [
        ("admin", "admin@fraudmon.io", "System Admin", UserRole.ADMIN),
        ("analyst", "analyst@fraudmon.io", "Fraud Analyst", UserRole.ANALYST),
        ("alice", "alice@example.com", "Alice Customer", UserRole.CUSTOMER),
        ("bob", "bob@example.com", "Bob Customer", UserRole.CUSTOMER),
    ]
    for username, email, name, role in seed:
        user = _ensure_user(db, username, email, name, role)
        accounts = list(
            db.execute(select(Account).where(Account.user_id == user.id)).scalars()
        )
        if not accounts:
            for atype in (AccountType.CHECKING, AccountType.SAVINGS):
                db.add(
                    Account(
                        user_id=user.id,
                        account_number=str(random.randrange(10**15, 10**16)),
                        account_type=atype,
                        balance=random.randint(1500, 25_000),
                        opened_at=datetime.now() - timedelta(days=random.randint(30, 900)),
                    )
                )
    db.commit()
    print("Seeded demo users: admin/analyst/alice/bob (password: password123)")


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_rules(db)
        seed_users_and_accounts(db)
    finally:
        db.close()
    print("Seed complete.")


if __name__ == "__main__":
    main()