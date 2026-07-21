from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from jose import JWTError, jwt

from package.common.auth.blacklist import is_blacklisted
from package.common.settings import get_settings
from package.common.utils.datetime import utc_now_aware


def _now() -> datetime:
    return utc_now_aware()


def create_access_token(subject: str, extra: Optional[dict[str, Any]] = None) -> str:
    settings = get_settings()
    expire = _now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "type": "access", "exp": expire, "jti": str(uuid4())}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    expire = _now() + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": subject, "type": "refresh", "exp": expire, "jti": str(uuid4())}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, check_blacklist: bool = True) -> Optional[dict[str, Any]]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if check_blacklist and is_blacklisted(payload.get("jti")):
        return None
    return payload


def create_token_pair(user_id: int, role: str) -> dict[str, Any]:
    settings = get_settings()
    subject = str(user_id)
    access = create_access_token(subject, {"role": role})
    refresh = create_refresh_token(subject)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }
