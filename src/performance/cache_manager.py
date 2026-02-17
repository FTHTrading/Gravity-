"""
Cache Manager – Deterministic cache with hash-based invalidation.

Phase VII: Scalability & Performance

Capabilities:
  - In-memory LRU cache for equation analysis results
  - SHA-256 keyed entries (deterministic cache keys)
  - TTL-based expiration
  - Manual invalidation
  - Cache statistics
"""

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, Any

from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class CacheStats:
    """Cache performance statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "max_size": self.max_size,
            "hit_rate": round(self.hit_rate, 4),
        }


class CacheManager:
    """
    Deterministic LRU cache with SHA-256-keyed entries.

    Cache keys are always computed as SHA-256(canonical_input) to ensure
    deterministic behavior regardless of input formatting.
    """

    def __init__(self, max_size: int = 1024, ttl_seconds: int = 3600):
        """
        Args:
            max_size: Maximum number of cache entries
            ttl_seconds: Time-to-live in seconds (0 = no expiry)
        """
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: dict = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._stats = CacheStats(max_size=max_size)

    @staticmethod
    def make_key(*args) -> str:
        """Compute deterministic cache key from arguments."""
        combined = "|".join(str(a) for a in args)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a cached value by key.

        Returns None on miss or expired entry.
        """
        if key not in self._cache:
            self._stats.misses += 1
            return None

        # Check TTL
        if self._ttl > 0:
            ts = self._timestamps.get(key, 0)
            if time.monotonic() - ts > self._ttl:
                # Expired
                self._evict(key)
                self._stats.misses += 1
                return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._stats.hits += 1
        return self._cache[key]

    def put(self, key: str, value: Any):
        """Store a value in the cache."""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            # Evict LRU if at capacity
            while len(self._cache) >= self._max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                self._timestamps.pop(evicted_key, None)
                self._stats.evictions += 1

        self._cache[key] = value
        self._timestamps[key] = time.monotonic()
        self._stats.size = len(self._cache)

    def invalidate(self, key: str):
        """Remove a specific entry."""
        self._evict(key)

    def invalidate_all(self):
        """Clear entire cache."""
        self._cache.clear()
        self._timestamps.clear()
        self._stats.size = 0
        log.info("Cache cleared")

    def _evict(self, key: str):
        """Remove an entry from cache."""
        if key in self._cache:
            del self._cache[key]
            self._timestamps.pop(key, None)
            self._stats.evictions += 1
            self._stats.size = len(self._cache)

    @property
    def stats(self) -> CacheStats:
        self._stats.size = len(self._cache)
        return self._stats

    def contains(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        if key not in self._cache:
            return False
        if self._ttl > 0:
            ts = self._timestamps.get(key, 0)
            if time.monotonic() - ts > self._ttl:
                self._evict(key)
                return False
        return True
