"""Auth deps — package JWT + local User."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.models.enums import UserRole
from app.models.user import User
from package.common.auth import AccessToken, OptionalAccessToken, load_user, require_roles
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


def get_user_optional(session: SessionDep, token: OptionalAccessToken) -> User | None:
    if not token:
        return None
    try:
        return load_user(session, token, User)
    except Exception:
        return None


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


def get_delivery_user(
    session: SessionDep,
    token: Annotated[dict, Depends(require_roles(UserRole.DELIVERY.value))],
) -> User:
    return load_user(session, token, User)


def get_customer_user(
    session: SessionDep,
    token: Annotated[dict, Depends(require_roles(UserRole.CUSTOMER.value))],
) -> User:
    return load_user(session, token, User)


CurrentUser = Annotated[User, Depends(get_user)]
OptionalUser = Annotated[User | None, Depends(get_user_optional)]
AdminUser = Annotated[User, Depends(get_admin_user)]
RetailerUser = Annotated[User, Depends(get_retailer_user)]
DeliveryUser = Annotated[User, Depends(get_delivery_user)]
CustomerUser = Annotated[User, Depends(get_customer_user)]
