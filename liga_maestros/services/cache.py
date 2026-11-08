"""Small JSON cache with Redis support and a bounded in-process fallback."""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any

redis_module: Any = None
try:
    import redis as redis_module
except ImportError:  # pragma: no cover - exercised when the optional extra is absent
    pass

logger = logging.getLogger(__name__)


class CacheService:
    """Use Redis when configured, otherwise keep short-lived values in memory."""

    _REDIS_PREFIX = "liga-maestros:"

    def __init__(self, host="localhost", port=6379, db=0, default_ttl=300, max_entries=1024):
        self.default_ttl = max(1, int(default_ttl))
        self.max_entries = max(1, int(max_entries))
        self._local_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._local_cache_lock = threading.RLock()
        self.client = None
        self.backend = "memory"

        redis_url = os.getenv("REDIS_URL", "").strip()
        redis_enabled = os.getenv("REDIS_ENABLED", "").strip().lower() in {"1", "true", "yes"}
        if redis_module is None or (not redis_url and not redis_enabled):
            return

        try:
            client_options = {"decode_responses": True, "socket_connect_timeout": 1, "socket_timeout": 1}
            if redis_url:
                self.client = redis_module.Redis.from_url(redis_url, **client_options)
            else:
                self.client = redis_module.Redis(host=host, port=port, db=db, **client_options)
            self.client.ping()
            self.backend = "redis"
        except Exception as exc:  # pragma: no cover - depends on external Redis
            logger.warning("Redis is unavailable; using the local cache: %s", exc)
            self.client = None

    def get(self, key: str) -> Any | None:
        if self.backend == "redis":
            try:
                data = self.client.get(self._redis_key(key))
            except Exception as exc:  # Keep the API available during Redis outages.
                self._use_memory_fallback(exc)
            else:
                if data is None:
                    return None
                try:
                    return json.loads(data)
                except (TypeError, ValueError):
                    logger.warning("Discarding invalid JSON from cache key %s", key)
                    self.delete(key)
                    return None

        with self._local_cache_lock:
            entry = self._local_cache.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= time.monotonic():
                self._local_cache.pop(key, None)
                return None
            self._local_cache.move_to_end(key)
            return copy.deepcopy(value)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        effective_ttl = self.default_ttl if ttl is None else int(ttl)
        if effective_ttl <= 0:
            self.delete(key)
            return

        serialized = json.dumps(value, separators=(",", ":"))
        if self.backend == "redis":
            try:
                self.client.setex(self._redis_key(key), effective_ttl, serialized)
                return
            except Exception as exc:  # Keep the API available during Redis outages.
                self._use_memory_fallback(exc)

        with self._local_cache_lock:
            self._local_cache[key] = (time.monotonic() + effective_ttl, copy.deepcopy(value))
            self._local_cache.move_to_end(key)
            while len(self._local_cache) > self.max_entries:
                self._local_cache.popitem(last=False)

    def delete(self, key: str) -> None:
        if self.backend == "redis":
            try:
                self.client.delete(self._redis_key(key))
            except Exception as exc:  # Keep the API available during Redis outages.
                self._use_memory_fallback(exc)

        with self._local_cache_lock:
            self._local_cache.pop(key, None)

    def clear(self) -> None:
        """Clear only this application's Redis keys, never a shared Redis DB."""
        if self.backend == "redis":
            try:
                keys = self.client.scan_iter(match=f"{self._REDIS_PREFIX}*")
                for key in keys:
                    self.client.delete(key)
            except Exception as exc:  # Keep the API available during Redis outages.
                self._use_memory_fallback(exc)

        with self._local_cache_lock:
            self._local_cache.clear()

    def _redis_key(self, key: str) -> str:
        return f"{self._REDIS_PREFIX}{key}"

    def _use_memory_fallback(self, exc: Exception) -> None:
        logger.warning("Redis connection failed; falling back to local memory: %s", exc)
        self.backend = "memory"
        self.client = None


cache = CacheService()
