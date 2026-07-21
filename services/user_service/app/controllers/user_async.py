"""Async OOP HTTP controller for user profile."""
from __future__ import annotations
from typing import Any, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_async import UserAsyncService
from package.common.base import BaseController


class UserController(BaseController):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UserAsyncService(session))

    async def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await self.service.call(fn, *args, **kwargs)
