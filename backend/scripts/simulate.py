"""Synthetic traffic generator: pumps a burst of realistic + suspicious
transactions through the live API to exercise the rule engine, velocity checks,
ML scoring and the alert feed.

Usage (with the backend running):
    python -m scripts.simulate --base http://localhost:8000/api/v1 --burst 200 --fraud_rate 0.2
"""

from __future__ import annotations

import argparse
import random
import sys

import httpx

from app.schemas import TxnType

CITIES = [
    ("New York", 40.7128, -74.0060),
    ("London", 51.5074, -0.1278),
    ("Singapore", 1.3521, 103.8198),
    ("Tokyo", 35.6762, 139.6503),
    ("Sydney", -33.8688, 151.2093),
    ("Cairo", 30.0444, 31.2357),
]

BEGINNER_TYPES = [TxnType.DEPOSIT, TxnType.WITHDRAWAL, TxnType.TRANSFER, TxnType.PAYMENT]


def _login(base: str, username: str, password: str) -> dict:
    res = httpx.post(f"{base}/auth/login", json={"username": username, "password": password})
    res.raise_for_status()
    return res.json()


def _accounts(base: str, token: str) -> list[dict]:
    res = httpx.get(
        f"{base}/accounts", headers={"Authorization": f"Bearer {token}"}, timeout=10
    )
    res.raise_for_status()
    return res.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fraud monitor traffic simulator")
    parser.add_argument("--base", default="http://localhost:8000/api/v1")
    parser.add_argument("--burst", type=int, default=200)
    parser.add_argument("--fraud-rate", type=float, default=0.2, help="share of suspicious patterns")
    parser.add_argument("--username", default="alice")
    parser.add_argument("--password", default="password123")
    args = parser.parse_args()

    token = _login(args.base, args.username, args.password)["access_token"]
    accounts = _accounts(args.base, token)
    if not accounts:
        print("No accounts found for user; run scripts.seed first.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}
    rng = random.Random(7)

    outcome_counts = {"approved": 0, "flagged": 0, "rejected": 0}
    print(f"Simulating {args.burst} transactions against {args.base}")

    for i in range(args.burst):
        acct = rng.choice(accounts)
        city, lat, lon = rng.choice(CITIES)
        fraudulent = rng.random() < args.fraud_rate

        if fraudulent:
            txn_type = rng.choice([TxnType.WITHDRAWAL, TxnType.TRANSFER, TxnType.PAYMENT])
            amount = round(rng.uniform(5000, 40_000), 2)
            device = "device-attacker-0001"
            # attacker bounces between far-apart cities quickly
            city, lat, lon = rng.choice([("Tokyo", 35.6762, 139.6503), ("Sydney", -33.8688, 151.2093)])
        else:
            txn_type = rng.choice(BEGINNER_TYPES)
            amount = round(rng.uniform(5, 1500), 2)
            device = f"device-{acct['id'][:8]}"

        payload = {
            "account_id": acct["id"],
            "txn_type": txn_type.value,
            "amount": amount,
            "channel": "mobile",
            "device_fingerprint": device,
            "device_name": "Sim Phone",
            "device_type": "smartphone",
            "os": "sim-os",
            "latitude": lat,
            "longitude": lon,
            "city": city,
            "country": "SYM",
            "ip_address": "203.0.113.7",
        }
        res = httpx.post(f"{args.base}/transactions", json=payload, headers=headers, timeout=15)
        if res.status_code != 201:
            print(f"  ! {res.status_code}: {res.text[:120]}")
            continue
        decision = res.json()
        status = decision["status"]
        outcome_counts[status] = outcome_counts.get(status, 0) + 1
        if i % 20 == 0 or status != "approved":
            print(
                f"  tx#{i:03d} {txn_type.value:>9} ${amount:>9,.2f} "
                f"-> {status:>8} risk={decision['risk_score']:>3} "
                f"reasons={[r['code'] for r in decision['decision_reasons'][:3]]}"
            )

    print("\nSummary:", outcome_counts)
    print("Check the analyst dashboard for alerts and the /api/v1/stream/alerts feed.")


if __name__ == "__main__":
    main()