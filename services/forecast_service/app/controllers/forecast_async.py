"""Async OOP HTTP controller — thin adapter over sync domain modules."""
from __future__ import annotations
from typing import Any, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.forecast_async import ForecastAsyncService
from package.common.base import BaseController

class ForecastController(BaseController):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ForecastAsyncService(session))

    async def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await self.service.call(fn, *args, **kwargs)
