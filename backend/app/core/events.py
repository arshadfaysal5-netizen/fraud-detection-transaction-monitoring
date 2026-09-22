"""In-process pub/sub for real-time dashboard feeds (SSE).

Bridge between the sync service layer (which runs under threadpool) and the
asyncio event loop serving SSE streams.
"""

import asyncio
import json
import logging

logger = logging.getLogger(__name__)

MAX_SUBSCRIBERS = 64


class AlertHub:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._queue = asyncio.Queue(maxsize=10_000)
        logger.info("Alert hub attached to event loop")

    def publish(self, event: dict) -> None:
        if self._loop is None or self._queue is None:
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, json.dumps(event, default=str))

    def subscribe(self):
        if self._queue is None:
            raise RuntimeError("Alert hub not attached")
        return self._queue

    @property
    def available(self) -> bool:
        return self._loop is not None and self._queue is not None


hub = AlertHub()