"""Per-client token bucket (the global refresh cooldown and single-flight lock live in refresh.py)."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

MAX_TRACKED_CLIENTS = 10_000


@dataclass
class _Bucket:
    tokens: float
    updated: float


class TokenBucketLimiter:
    def __init__(self, capacity: int, window_seconds: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.capacity = float(capacity)
        self.refill_per_second = capacity / window_seconds
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str) -> tuple[bool, int]:
        """(allowed, retry_after_seconds). retry_after is 0 when allowed."""
        now = self._clock()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= MAX_TRACKED_CLIENTS:
                    self._prune_locked(now)
                bucket = _Bucket(self.capacity, now)
                self._buckets[key] = bucket
            else:
                bucket.tokens = min(self.capacity, bucket.tokens + (now - bucket.updated) * self.refill_per_second)
                bucket.updated = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0
            deficit = 1.0 - bucket.tokens
            return False, max(1, math.ceil(deficit / self.refill_per_second))

    def _prune_locked(self, now: float) -> None:
        full = [
            k
            for k, b in self._buckets.items()
            if b.tokens + (now - b.updated) * self.refill_per_second >= self.capacity
        ]
        for k in full:
            del self._buckets[k]
        if len(self._buckets) >= MAX_TRACKED_CLIENTS:
            self._buckets.clear()
