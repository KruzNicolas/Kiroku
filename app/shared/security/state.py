from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class IdempotencyRecord:
    expires_at: float
    status_code: int
    body: Any


class InMemoryIdempotencyStore:
    def __init__(self):
        self._records: dict[str, IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> IdempotencyRecord | None:
        now = time.time()
        with self._lock:
            self._cleanup_locked(now)
            return self._records.get(key)

    def set(self, key: str, status_code: int, body: Any, ttl_seconds: int) -> None:
        now = time.time()
        with self._lock:
            self._cleanup_locked(now)
            self._records[key] = IdempotencyRecord(
                expires_at=now + ttl_seconds,
                status_code=status_code,
                body=body,
            )

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def _cleanup_locked(self, now: float) -> None:
        expired = [k for k, v in self._records.items() if v.expires_at <= now]
        for key in expired:
            self._records.pop(key, None)


class InMemoryRateLimiter:
    def __init__(self):
        self._counts: dict[tuple[str, str, int], int] = {}
        self._lock = threading.Lock()

    def allow(self, source: str, path: str, limit_per_min: int) -> tuple[bool, int]:
        now = time.time()
        window = int(now // 60)
        retry_after = int((window + 1) * 60 - now)
        key = (source, path, window)

        with self._lock:
            self._cleanup_locked(window)
            current = self._counts.get(key, 0)
            if current >= limit_per_min:
                return False, max(1, retry_after)
            self._counts[key] = current + 1
            return True, max(1, retry_after)

    def clear(self) -> None:
        with self._lock:
            self._counts.clear()

    def _cleanup_locked(self, current_window: int) -> None:
        stale = [k for k in self._counts.keys() if k[2] < current_window]
        for key in stale:
            self._counts.pop(key, None)


idempotency_store = InMemoryIdempotencyStore()
rate_limiter = InMemoryRateLimiter()
