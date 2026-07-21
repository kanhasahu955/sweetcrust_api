from __future__ import annotations
from fastapi import APIRouter
from app.controllers import inventory as ctrl
from app.deps import AsyncSessionDep, AdminUser
from app.schemas.admin import StockUpdateIn
from package.common.schemas import ok

from app.controllers.inventory_async import InventoryController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await InventoryController(session).call(fn, *args, **kwargs)
router = APIRouter(prefix="/admin", tags=["inventory"])

@router.get("/inventory")
async def get_inventory(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.summary))

@router.get("/inventory/low-stock")
async def get_inventory_low_stock(session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.low_stock))

@router.get("/inventory/movements")
async def get_inventory_movements(session: AsyncSessionDep, _: AdminUser, product_id: int | None = None, limit: int = 50):
    return ok(await _domain(session, ctrl.movements, product_id, limit))

@router.patch("/products/{product_id}/stock")
async def patch_product_id_stock(product_id: int, body: StockUpdateIn, session: AsyncSessionDep, admin: AdminUser):
    return ok(await _domain(session, ctrl.update_stock, product_id, body.stock_qty, body.reason or "adjust", body.note, admin.id))
