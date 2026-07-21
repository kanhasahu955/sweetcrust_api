"""OOP bases for microservices — Repository → Service → Controller."""
from __future__ import annotations

from typing import Any, Callable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository:
    """Data-access boundary. Subclass per aggregate."""

    __slots__ = ("session",)

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_sync(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Bridge sync SQLModel helpers during migration."""

        def _call(sync_session):
            return fn(sync_session, *args, **kwargs)

        return await self.session.run_sync(_call)


class BaseService:
    """Domain / use-case layer. Owns business rules."""

    __slots__ = ("session",)

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_sync(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        def _call(sync_session):
            return fn(sync_session, *args, **kwargs)

        return await self.session.run_sync(_call)


class BaseController:
    """HTTP adapter — thin, no SQL. Calls a service."""

    __slots__ = ("service",)

    def __init__(self, service: BaseService) -> None:
        self.service = service
