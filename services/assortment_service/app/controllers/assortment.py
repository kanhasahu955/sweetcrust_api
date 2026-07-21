"""Assortment HTTP controller (async OOP)."""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.assortment import AssortmentService
from package.common.base import BaseController

class AssortmentController(BaseController):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AssortmentService(session))

    async def status(self):
        return {"service": "assortment", "ready": True, "mode": "async-oop"}

    async def list_products(self, **kwargs):
        return await self.service.list_range(**kwargs)

    async def patch_product(self, product_id: int, data: dict):
        return await self.service.set_flags(product_id, **data)

    async def available(self):
        return await self.service.available()

    async def retailer_catalog(self):
        return await self.service.retailer_catalog()
