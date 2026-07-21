"""Assortment product repository (async)."""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.catalog import Category, Product
from package.common.base import BaseRepository
from package.common.utils import utc_now

class ProductRepository(BaseRepository):
    async def get(self, product_id: int) -> Product | None:
        return await self.session.get(Product, product_id)

    async def get_category(self, category_id: int) -> Category | None:
        return await self.session.get(Category, category_id)

    async def list_all(self) -> list[Product]:
        result = await self.session.execute(select(Product).order_by(Product.updated_at.desc()))
        return list(result.scalars().all())

    async def list_sellable(self) -> list[Product]:
        result = await self.session.execute(
            select(Product).where(Product.is_active == True, Product.is_draft == False, Product.stock_qty > 0)  # noqa: E712
        )
        return list(result.scalars().all())

    async def list_active(self) -> list[Product]:
        result = await self.session.execute(
            select(Product).where(Product.is_active == True, Product.is_draft == False)  # noqa: E712
        )
        return list(result.scalars().all())

    async def save(self, product: Product) -> Product:
        product.updated_at = utc_now()
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product
