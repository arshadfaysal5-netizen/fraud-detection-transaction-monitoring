import logging
import time
import threading

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class LocalTTLCache:
    """In-memory TTL store used when Redis is unreachable (local dev / CI)."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        with self._lock:
            val = self._read(key)
            val = int(val) + amount
            self._data[key] = (self._expires(ttl), val)
            return val

    def incrbyfloat(self, key: str, amount: float, ttl: int | None = None) -> float:
        with self._lock:
            val = self._read(key)
            val = float(val) + amount
            self._data[key] = (self._expires(ttl), val)
            return val

    def get(self, key: str) -> float | int | None:
        with self._lock:
            return self._read(key)

    def lpush(self, key: str, value: str) -> int:
        with self._lock:
            if self._data.get(key):
                expires, lst = self._data[key]
                lst = list(lst) if isinstance(lst, list) else []
            else:
                expires, lst = self._expires(), []
            lst.insert(0, value)
            self._data[key] = (expires, lst[:20])
            return len(lst)

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        with self._lock:
            expires, lst = self._data.get(key, (self._expires(), []))
            if expires and expires < time.monotonic():
                return []
            return [str(v) for v in lst[start : end + 1]]

    def setex(self, key: str, ttl: int, value: float | str) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + ttl, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def _read(self, key: str) -> object:
        expires, val = self._data.get(key, (0.0, 0))
        if expires and expires < time.monotonic():
            self._data.pop(key, None)
            return 0
        return val

    def _expires(self, ttl: int | None = None) -> float:
        return time.monotonic() + (ttl or settings.redis_ttl_velocity)


class RedisClient:
    """Thin wrapper with graceful degradation to LocalTTLCache."""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None
        self._fallback = LocalTTLCache()
        self._checked = False

    def _connect(self):
        if not self._checked:
            self._checked = True
            try:
                self._client = redis.Redis.from_url(
                    settings.redis_url, socket_connect_timeout=1, decode_responses=True
                )
                self._client.ping()
                logger.info("Connected to Redis at %s", settings.redis_url)
            except Exception as exc:  # noqa: BLE001
                self._client = None
                logger.warning("Redis unavailable (%s); using in-memory fallback cache", exc)

    @property
    def client(self) -> redis.Redis | LocalTTLCache:
        self._connect()
        return self._client or self._fallback

    @property
    def is_redis(self) -> bool:
        self._connect()
        return self._client is not None


redis_client = RedisClient()


def get_redis() -> redis.Redis | LocalTTLCache:
    return redis_client.client