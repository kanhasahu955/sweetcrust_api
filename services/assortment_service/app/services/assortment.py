"""Assortment domain service (async OOP)."""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.products import ProductRepository
from package.common.base import BaseService
from package.common.errors import NotFoundError

class AssortmentService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = ProductRepository(session)

    async def list_range(self, *, q: str | None = None, active: bool | None = None,
                         draft: bool | None = None, page: int = 1, page_size: int = 50) -> dict:
        rows = await self.repo.list_all()
        if q:
            ql = q.lower()
            rows = [
                p
                for p in rows
                if ql in (p.name or "").lower() or ql in (getattr(p, "brand_name", None) or "").lower()
            ]
        if active is not None:
            rows = [p for p in rows if bool(p.is_active) is active]
        if draft is not None:
            rows = [p for p in rows if bool(p.is_draft) is draft]
        start = max(0, (page - 1) * page_size)
        return {"items": rows[start:start + page_size], "total": len(rows), "page": page}

    async def set_flags(self, product_id: int, **flags):
        p = await self.repo.get(product_id)
        if not p:
            raise NotFoundError("Product not found")
        for key in ("is_active", "is_draft", "is_trending", "is_bestseller"):
            if key in flags and flags[key] is not None:
                setattr(p, key, flags[key])
        if flags.get("category_id") is not None:
            if not await self.repo.get_category(flags["category_id"]):
                raise NotFoundError("Category not found")
            p.category_id = flags["category_id"]
        return await self.repo.save(p)

    async def available(self):
        return await self.repo.list_sellable()

    async def retailer_catalog(self):
        return await self.repo.list_active()
