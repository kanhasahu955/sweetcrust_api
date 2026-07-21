"""Shared Redis rate limit helper for all services."""
from __future__ import annotations

from package.common.errors import RateLimitError


def enforce_rate(key: str, *, limit: int, window_sec: int) -> int | None:
    """
    Increment `key` with TTL window. Raises RateLimitError when over limit.
    Returns current count, or None if Redis unavailable (fail-open).
    """
    if limit <= 0:
        return None
    try:
        from package.redis import redis_incr

        n = redis_incr(key, window_sec)
    except Exception:
        return None
    if n is not None and n > limit:
        raise RateLimitError(f"Rate limit exceeded ({limit}/{window_sec}s)")
    return n
