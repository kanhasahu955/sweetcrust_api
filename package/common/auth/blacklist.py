"""JWT revoke list — Redis when available, in-process fallback otherwise."""
from __future__ import annotations

import logging
import time
from typing import Optional

from jose import jwt

from package.common.settings import get_settings
from package.redis.client import redis_get, redis_set

logger = logging.getLogger(__name__)

# ponytail: process-local fallback — lost on restart; upgrade = Redis required in prod
_memory: dict[str, float] = {}


def _purge_memory() -> None:
    now = time.time()
    dead = [k for k, exp in _memory.items() if exp <= now]
    for k in dead:
        _memory.pop(k, None)


def blacklist_jti(jti: str, ttl_seconds: int) -> None:
    if not jti or ttl_seconds <= 0:
        return
    key = f"jwt:bl:{jti}"
    if redis_set(key, "1", ttl_seconds):
        return
    _purge_memory()
    _memory[jti] = time.time() + ttl_seconds


def is_blacklisted(jti: Optional[str]) -> bool:
    if not jti:
        return False
    if redis_get(f"jwt:bl:{jti}") == "1":
        return True
    exp = _memory.get(jti)
    if exp is None:
        return False
    if exp <= time.time():
        _memory.pop(jti, None)
        return False
    return True


def blacklist_token(token: str) -> bool:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
    except Exception:
        return False
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return False
    ttl = int(exp - time.time())
    if ttl <= 0:
        return True
    blacklist_jti(str(jti), ttl)
    return True
