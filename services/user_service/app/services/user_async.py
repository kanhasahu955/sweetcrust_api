"""Async OOP facade — bridges sync profile use-cases via run_sync."""
from __future__ import annotations
from typing import Any, Callable
from package.common.base import BaseService


class UserAsyncService(BaseService):
    async def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await self.run_sync(fn, *args, **kwargs)
