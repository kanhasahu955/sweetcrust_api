"""Auth deps — package JWT + local User."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.models.enums import UserRole
from app.models.user import User
from package.common.auth import AccessToken, load_user, require_roles
from package.database import SessionDep

__all__ = [
    "SessionDep",
    "CurrentUser",
    "OptionalUser",
    "AdminUser",
    "RetailerUser",
    "DeliveryUser",
    "CustomerUser",
]


def get_user(session: SessionDep, token: AccessToken) -> User:
    return load_user(session, token, User)


def get_optional_user(session: SessionDep, token: AccessToken | None = None) -> User | None:
    if not token:
        return None
    try:
        from package.common.auth import optional_access_token
    except Exception:
        return None
    return None


# Fixed optional via package
from package.common.auth import OptionalAccessToken


def get_user_optional(session: SessionDep, token: OptionalAccessToken) -> User | None:
    if not token:
        return None
    try:
        return load_user(session, token, User)
    except Exception:
        return None


def _role(role: str):
    def dep(session: SessionDep, token: Annotated[dict, Depends(require_roles(role))]) -> User:
        return load_user(session, token, User)

    return dep


CurrentUser = Annotated[User, Depends(get_user)]
OptionalUser = Annotated[User | None, Depends(get_user_optional)]
AdminUser = Annotated[User, Depends(_role(UserRole.ADMIN.value))]
RetailerUser = Annotated[User, Depends(_role(UserRole.RETAILER.value))]
DeliveryUser = Annotated[User, Depends(_role(UserRole.DELIVERY.value))]
CustomerUser = Annotated[User, Depends(_role(UserRole.CUSTOMER.value))]
