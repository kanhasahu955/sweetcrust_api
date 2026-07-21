"""Async OOP HTTP controller — thin adapter over sync domain modules."""
from __future__ import annotations
from typing import Any, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.tracking_async import TrackingAsyncService
from package.common.base import BaseController

class TrackingController(BaseController):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TrackingAsyncService(session))

    async def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await self.service.call(fn, *args, **kwargs)
