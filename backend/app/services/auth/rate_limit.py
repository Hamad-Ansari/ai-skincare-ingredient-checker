"""Small process-local rate limiter for authentication endpoints."""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable


class RateLimitExceeded(Exception):
    """Raised when an authentication rate-limit bucket is exhausted."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)
        super().__init__("Rate limit exceeded")


class InMemoryRateLimiter:
    """Fixed-window sliding log limiter; volatile and single-process by design."""

    def __init__(
        self, max_buckets: int = 10_000, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._buckets: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_buckets = max_buckets
        self._clock = clock

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        """Consume one attempt or raise with a bounded retry interval."""
        now = self._clock()
        bucket_key = hashlib.sha256(key.encode("utf-8")).hexdigest()
        cutoff = now - window_seconds

        with self._lock:
            attempts = self._buckets.setdefault(bucket_key, deque())
            self._buckets.move_to_end(bucket_key)
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()

            if len(attempts) >= limit:
                raise RateLimitExceeded(int(attempts[0] + window_seconds - now) + 1)

            attempts.append(now)
            while len(self._buckets) > self._max_buckets:
                self._buckets.popitem(last=False)

    def clear(self) -> None:
        """Clear all volatile buckets; intended for isolated tests only."""
        with self._lock:
            self._buckets.clear()


def rate_limit_auth_attempt(
    limiter: InMemoryRateLimiter,
    action: str,
    client_host: str,
    identifier: str | None = None,
) -> None:
    """Apply a bounded per-IP and per-account bucket without persisting identifiers."""
    limits = {
        "register": ((10, 3600), (3, 3600)),
        "login": ((30, 900), (10, 900)),
        "verification": ((10, 3600), (3, 3600)),
        "password_reset": ((10, 3600), (3, 3600)),
    }
    ip_limit, account_limit = limits[action]
    limiter.check(f"{action}:ip:{client_host}", *ip_limit)
    if identifier:
        limiter.check(f"{action}:account:{identifier}", *account_limit)
