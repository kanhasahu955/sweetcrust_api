"""Async OOP facade — bridges existing sync domain via AsyncSession.run_sync."""
from __future__ import annotations
from typing import Any, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from package.common.base import BaseService

class LocationAsyncService(BaseService):
    """Call sync use-cases without blocking the event loop incorrectly.

    ``run_sync`` executes on the connection's greenlet-compatible sync API.
    """

    async def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await self.run_sync(fn, *args, **kwargs)
