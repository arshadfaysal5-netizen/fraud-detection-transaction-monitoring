"""Async Kafka consumers for the deep pipeline.

The sync fast path already decides every transaction. These consumers thicken
the pipeline: they replay the ingest event, recompute the deep features,
re-score, reconcile status, bump risk profiles and publish the feature payload
for the ML retraining data lake.

Runs only when Kafka is reachable (started via app.main lifespan).
"""

from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select

from app.core.config import settings
from app.fraud.decision import decide
from app.fraud.ml import runner
from app.fraud.risk_score import combine_risk
from app.fraud.rules import evaluate_rules, rule_risk
from app.ml.common import vector_from_features
from app.models import Rule, Transaction
from app.core.db import SessionLocal

logger = logging.getLogger(__name__)

BACKOFF_START = 2.0


async def run_consumer() -> None:
    """Blocking consumer loop; retries connection with backoff."""
    consumer: AIOKafkaConsumer | None = None
    delay = BACKOFF_START
    while True:
        try:
            if consumer is None:
                consumer = AIOKafkaConsumer(
                    settings.kafka_topic_tx_ingest,
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    group_id=settings.kafka_consumer_group,
                    auto_offset_reset="earliest",
                    enable_auto_commit=False,
                )
                await consumer.start()
                logger.info("Fraud worker consuming %s", settings.kafka_topic_tx_ingest)
                delay = BACKOFF_START
            async for message in consumer:
                try:
                    event = json.loads(message.value.decode())
                    await handle_ingest(event)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Worker error processing event: %s", exc)
                await consumer.commit()
        except asyncio.CancelledError:
            if consumer is not None:
                await consumer.stop()
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Kafka consumer unavailable (%s); retrying in %ss", exc, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


async def handle_ingest(event: dict) -> None:
    """Deep pipeline for one transaction ingest event."""
    payload = event.get("payload", {})
    txn_id = payload.get("transaction_id")
    if not txn_id:
        return

    db = SessionLocal()
    try:
        txn = db.get(Transaction, txn_id)
        if txn is None:
            # can lag behind the sync path; treat as dropped
            return

        rule_rows = db.execute(select(Rule)).scalars().all()
        features = payload.get("features") or {}
        rule_hits = evaluate_rules(features, rule_rows)
        r_risk = rule_risk(rule_hits)

        ml_risk = None
        if runner.available:
            ml_risk = round(runner.predict_proba(features) * 100.0, 1)

        risk = combine_risk(r_risk, ml_risk)
        status = decide(risk)
        txn.risk_score = risk
        if status != txn.status:
            txn.status = status
        db.add(txn)
        db.commit()

        # ML retraining data lake
        from app.core.kafka import publish_event

        publish_event(
            "ml.features",
            "features.recorded",
            "transaction",
            txn_id,
            {"transaction_id": txn_id, "label": str(status.value), "vector": vector_from_features(features)},
        )
    finally:
        db.close()