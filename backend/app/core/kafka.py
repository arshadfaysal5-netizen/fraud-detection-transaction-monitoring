"""Kafka-based message bus with graceful degradation for local dev.

The bus owns an asyncio loop on a background thread. If Kafka is unreachable
it falls back to a no-op (events are logged) so the application still boots
locally. The async fraud worker is started separately (see app.workers).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid

from aiokafka import AIOKafkaProducer

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 5


class MessageBus:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._producer: AIOKafkaProducer | None = None
        self._thread: threading.Thread | None = None
        self._started = False
        self._use_kafka = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="kafka-bus", daemon=True)
        self._thread.start()

        future = asyncio.run_coroutine_threadsafe(self._connect(), self._loop)
        try:
            future.result(timeout=8)
        except TimeoutError:
            logger.warning("Kafka connect timed out; bus will run in stub mode")

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _connect(self) -> None:
        try:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    producer = AIOKafkaProducer(
                        bootstrap_servers=settings.kafka_bootstrap_servers,
                        loop=self._loop,
                        request_timeout_ms=4000,
                        retries=2,
                    )
                    await producer.start()
                    self._producer = producer
                    self._use_kafka = True
                    logger.info("Kafka producer connected to %s", settings.kafka_bootstrap_servers)
                    return
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Kafka try %d/%d failed: %s", attempt, MAX_RETRIES, exc)
                    await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
        self._use_kafka = False
        logger.warning("Kafka unreachable — message bus running in stub mode (logging only)")

    def publish(self, topic: str, key: str, payload: dict) -> None:
        if not self._started or self._loop is None:
            return
        value = json.dumps(payload, default=str).encode("utf-8")
        if self._use_kafka and self._producer is not None:
            asyncio.run_coroutine_threadsafe(
                self._producer.send(topic, value=value, key=str(key).encode()), self._loop
            )
        else:
            logger.debug("[stub-%s] %s", topic, payload.get("event", topic))

    def shard_key(self) -> str:
        return str(uuid.uuid4())


bus = MessageBus()


def publish_event(topic: str, event: str, entity: str, entity_id: str | None, payload: dict) -> None:
    bus.publish(
        topic,
        key=str(entity_id or entity),
        payload={
            "event": event,
            "entity": entity,
            "entity_id": entity_id,
            "ts": json.dumps(int(__import__("time").time())),
            "payload": payload,
        },
    )