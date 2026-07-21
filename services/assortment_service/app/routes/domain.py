"""Assortment domain routes — async handlers."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.controllers.assortment import AssortmentController
from app.deps import AdminUser, AsyncSessionDep, RetailerUser
from package.common.schemas import ok

router = APIRouter(tags=["assortment"])

class FlagsIn(BaseModel):
    is_active: bool | None = None
    is_draft: bool | None = None
    is_trending: bool | None = None
    is_bestseller: bool | None = None
    category_id: int | None = None

def get_ctrl(session: AsyncSessionDep) -> AssortmentController:
    return AssortmentController(session)

@router.get("/assortment/status")
async def status(ctrl: AssortmentController = Depends(get_ctrl)):
    return ok(await ctrl.status())

@router.get("/admin/assortment/products")
async def admin_list(
    _: AdminUser,
    q: str | None = None, active: bool | None = None, draft: bool | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    ctrl: AssortmentController = Depends(get_ctrl),
):
    return ok(await ctrl.list_products(q=q, active=active, draft=draft, page=page, page_size=page_size))

@router.patch("/admin/assortment/products/{product_id}")
async def admin_patch(product_id: int, body: FlagsIn, _: AdminUser, ctrl: AssortmentController = Depends(get_ctrl)):
    return ok(await ctrl.patch_product(product_id, body.model_dump(exclude_unset=True)))

@router.get("/admin/assortment/available")
async def admin_available(_: AdminUser, ctrl: AssortmentController = Depends(get_ctrl)):
    return ok(await ctrl.available())

@router.get("/retailer/assortment")
async def retailer_list(_: RetailerUser, ctrl: AssortmentController = Depends(get_ctrl)):
    return ok(await ctrl.retailer_catalog())
