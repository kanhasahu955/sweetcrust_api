"""Admin-service auth deps — package JWT + local User."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.models.enums import UserRole
from app.models.user import User
from package.common.auth import AccessToken, load_user, require_roles
from package.database import SessionDep

__all__ = ["SessionDep", "CurrentUser", "AdminUser", "RetailerUser", "get_user"]


def get_user(session: SessionDep, token: AccessToken) -> User:
    return load_user(session, token, User)


def get_admin_user(
    session: SessionDep,
    token: Annotated[dict, Depends(require_roles(UserRole.ADMIN.value))],
) -> User:
    return load_user(session, token, User)


def get_retailer_user(
    session: SessionDep,
    token: Annotated[dict, Depends(require_roles(UserRole.RETAILER.value))],
) -> User:
    return load_user(session, token, User)


CurrentUser = Annotated[User, Depends(get_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
RetailerUser = Annotated[User, Depends(get_retailer_user)]
