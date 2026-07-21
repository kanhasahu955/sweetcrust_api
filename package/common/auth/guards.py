"""Auth guards — validate JWT access token; return claims (not ORM User).

Each service loads its own User from `sub` after this guard.
"""
from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from package.common.auth.jwt import decode_token

bearer = HTTPBearer(auto_error=False)


def require_access_token(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)],
) -> dict[str, Any]:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access" or payload.get("sub") is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked token")
    return payload


def optional_access_token(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)],
) -> Optional[dict[str, Any]]:
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access" or payload.get("sub") is None:
        return None
    return payload


def require_roles(*roles: str):
    """Dependency factory: access token must include one of `roles`."""

    def _guard(payload: Annotated[dict[str, Any], Depends(require_access_token)]) -> dict[str, Any]:
        role = str(payload.get("role") or "")
        if role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return payload

    return _guard


AccessToken = Annotated[dict[str, Any], Depends(require_access_token)]
OptionalAccessToken = Annotated[Optional[dict[str, Any]], Depends(optional_access_token)]
