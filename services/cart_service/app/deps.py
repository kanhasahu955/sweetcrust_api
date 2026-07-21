"""Async auth deps — JWT → User via AsyncSession."""
from __future__ import annotations
from app.models.user import User
from package.common.auth import make_async_user_deps
from package.database import AsyncSessionDep

_deps = make_async_user_deps(User)
CurrentUser = _deps["CurrentUser"]
OptionalUser = _deps["OptionalUser"]
AdminUser = _deps["for_roles"]("admin")
RetailerUser = _deps["for_roles"]("retailer")
DeliveryUser = _deps["for_roles"]("delivery")
CustomerUser = _deps["for_roles"]("customer")

__all__ = [
    "AsyncSessionDep", "CurrentUser", "OptionalUser",
    "AdminUser", "RetailerUser", "DeliveryUser", "CustomerUser",
]
