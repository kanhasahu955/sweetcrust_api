"""Simple Redis distributed locks."""
from __future__ import annotations

import uuid
from contextlib import contextmanager

from package.redis.client import get_redis


@contextmanager
def redis_lock(name: str, ttl_seconds: int = 30):
    """Best-effort lock. Yields True if acquired, False otherwise."""
    r = get_redis()
    token = str(uuid.uuid4())
    key = f"lock:{name}"
    acquired = False
    if r:
        try:
            acquired = bool(r.set(key, token, nx=True, ex=ttl_seconds))
        except Exception:
            acquired = False
    try:
        yield acquired
    finally:
        if acquired and r:
            try:
                if r.get(key) == token:
                    r.delete(key)
            except Exception:
                pass
