import json
import logging
from typing import Any, Optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

class CacheService:
    """Service for high-speed data caching with Redis support and local memory fallback."""
    
    def __init__(self, host='localhost', port=6379, db=0, default_ttl=300):
        self.default_ttl = default_ttl
        self._local_cache = {}
        if REDIS_AVAILABLE:
            try:
                self.client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
                self.client.ping()
                self.backend = 'redis'
            except Exception as e:
                logger.warning(f"Redis not available: {e}. Using local memory fallback.")
                self.backend = 'memory'
        else:
            self.backend = 'memory'

    def get(self, key: str) -> Optional[Any]:
        if self.backend == 'redis':
            data = self.client.get(key)
            return json.loads(data) if data else None
        return self._local_cache.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        serialized = json.dumps(value)
        if self.backend == 'redis':
            self.client.setex(key, ttl or self.default_ttl, serialized)
        else:
            self._local_cache[key] = value

    def delete(self, key: str):
        if self.backend == 'redis':
            self.client.delete(key)
        else:
            self._local_cache.pop(key, None)

    def clear(self):
        if self.backend == 'redis':
            self.client.flushdb()
        else:
            self._local_cache.clear()

cache = CacheService()
