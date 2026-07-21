"""Short-lived key/value for OAuth state when Redis is off."""
from __future__ import annotations

import time

from package.redis import redis_delete, redis_get, redis_set

# ponytail: process-local fallback — lost on restart; upgrade = Redis required in prod
_mem: dict[str, tuple[float, str]] = {}


def put(key: str, value: str, ttl_seconds: int = 600) -> None:
    _mem[key] = (time.time() + ttl_seconds, value)
    redis_set(key, value, ttl_seconds)


def pop(key: str) -> str | None:
    val = redis_get(key)
    redis_delete(key)
    item = _mem.pop(key, None)
    if val is not None:
        return val
    if not item:
        return None
    expires, value = item
    if time.time() > expires:
        return None
    return value
