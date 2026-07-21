"""Optional Redis helper (OTP cache, rate limits)."""

from __future__ import annotations

import logging
from typing import Optional

from package.common.settings import get_settings

logger = logging.getLogger(__name__)
_client = None
_failed = False


def get_redis():
    global _client, _failed
    if _failed:
        return None
    if _client is not None:
        return _client
    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        import redis

        _client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        _client.ping()
        return _client
    except Exception as exc:
        # Fail-open: OTP/rate-limit/JWT blacklist fall back to DB / in-memory
        logger.info("Redis skipped (app continues): %s", exc.__class__.__name__)
        _failed = True
        return None


def redis_set(key: str, value: str, ttl_seconds: int) -> bool:
    r = get_redis()
    if not r:
        return False
    try:
        r.setex(key, ttl_seconds, value)
        return True
    except Exception:
        logger.exception("redis_set failed")
        return False


def redis_get(key: str) -> Optional[str]:
    r = get_redis()
    if not r:
        return None
    try:
        return r.get(key)
    except Exception:
        logger.exception("redis_get failed")
        return None


def redis_delete(key: str) -> None:
    r = get_redis()
    if not r:
        return
    try:
        r.delete(key)
    except Exception:
        logger.exception("redis_delete failed")


def redis_delete_prefix(prefix: str) -> None:
    """Best-effort delete of keys matching prefix* (SCAN). Fail-open."""
    r = get_redis()
    if not r:
        return
    try:
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match=f"{prefix}*", count=100)
            if keys:
                r.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        logger.exception("redis_delete_prefix failed")


def redis_incr(key: str, ttl_seconds: int) -> int | None:
    """Increment counter; set TTL on first hit. Returns new count or None if Redis down."""
    r = get_redis()
    if not r:
        return None
    try:
        count = r.incr(key)
        if count == 1:
            r.expire(key, ttl_seconds)
        return int(count)
    except Exception:
        logger.exception("redis_incr failed")
        return None


def redis_ping() -> bool:
    r = get_redis()
    if not r:
        return False
    try:
        return bool(r.ping())
    except Exception:
        return False


def redis_publish(channel: str, payload: dict) -> bool:
    """Publish JSON payload to a Redis channel (realtime bridge). Fail-open."""
    import json

    r = get_redis()
    if not r:
        return False
    try:
        r.publish(channel, json.dumps(payload, default=str))
        return True
    except Exception:
        logger.exception("redis_publish failed channel=%s", channel)
        return False

