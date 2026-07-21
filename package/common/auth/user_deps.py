"""Build JWT → ORM User dependencies for any service's User model."""
from __future__ import annotations

from typing import Annotated, Any, TypeVar

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from package.common.auth.guards import AccessToken, OptionalAccessToken
from package.common.errors import UnauthorizedError
from package.database import SessionDep
from package.database.async_session import AsyncSessionDep

UserT = TypeVar("UserT")


def load_user(session: SessionDep, token: AccessToken, user_model: type[UserT]) -> UserT:
    try:
        uid = int(token["sub"])
    except (TypeError, ValueError, KeyError):
        raise UnauthorizedError("Invalid token subject")
    user = session.get(user_model, uid)
    if not user or not getattr(user, "is_active", True):
        raise UnauthorizedError("User not found")
    return user


async def load_user_async(
    session: AsyncSession,
    token: AccessToken,
    user_model: type[UserT],
) -> UserT:
    try:
        uid = int(token["sub"])
    except (TypeError, ValueError, KeyError):
        raise UnauthorizedError("Invalid token subject")
    user = await session.get(user_model, uid)
    if not user or not getattr(user, "is_active", True):
        raise UnauthorizedError("User not found")
    return user


def make_async_user_deps(user_model: type[UserT]) -> dict[str, Any]:
    """Async JWT → User deps for OOP/async services."""

    async def get_current(session: AsyncSessionDep, token: AccessToken) -> UserT:
        return await load_user_async(session, token, user_model)

    async def get_optional(session: AsyncSessionDep, token: OptionalAccessToken) -> UserT | None:
        if not token:
            return None
        try:
            return await load_user_async(session, token, user_model)
        except Exception:
            return None

    CurrentUser = Annotated[user_model, Depends(get_current)]  # type: ignore[valid-type]
    OptionalUser = Annotated[user_model | None, Depends(get_optional)]  # type: ignore[valid-type]

    def for_roles(*roles: str):
        # Inline role check — nested Depends(require_roles(...)) breaks OpenAPI ForwardRefs.
        async def _get(session: AsyncSessionDep, token: AccessToken) -> UserT:
            if str(token.get("role") or "") not in roles:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
            return await load_user_async(session, token, user_model)

        return Annotated[user_model, Depends(_get)]  # type: ignore[valid-type]

    return {
        "CurrentUser": CurrentUser,
        "OptionalUser": OptionalUser,
        "for_roles": for_roles,
        "get_current": get_current,
    }


def make_user_deps(user_model: type[UserT], *, role_attr: str = "value") -> dict[str, Any]:
    """
    Returns Annotated deps: CurrentUser, and role helpers via `role("admin")`.

        deps = make_user_deps(User)
        CurrentUser = deps["CurrentUser"]
        AdminUser = deps["for_roles"]("admin")
    """

    def get_current(session: SessionDep, token: AccessToken) -> UserT:
        return load_user(session, token, user_model)

    CurrentUser = Annotated[user_model, Depends(get_current)]  # type: ignore[valid-type]

    def for_roles(*roles: str):
        def _get(session: SessionDep, token: AccessToken) -> UserT:
            if str(token.get("role") or "") not in roles:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
            return load_user(session, token, user_model)

        return Annotated[user_model, Depends(_get)]  # type: ignore[valid-type]

    return {"CurrentUser": CurrentUser, "for_roles": for_roles, "get_current": get_current}
