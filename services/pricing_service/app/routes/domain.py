from __future__ import annotations
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from app.controllers import pricing as ctrl
from app.deps import AsyncSessionDep, AdminUser
from package.common.schemas import ok

from app.controllers.pricing_async import PricingController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await PricingController(session).call(fn, *args, **kwargs)
router = APIRouter(tags=["pricing"])

class BulkIn(BaseModel):
    product_ids: list[int] = Field(min_length=1)
    channel: str = "customer"

class PricesIn(BaseModel):
    selling_price: float | None = None
    customer_price: float | None = None
    shop_price: float | None = None
    original_price: float | None = None
    purchase_cost: float | None = None
    discount_percent: float | None = None
    gst_rate: float | None = None

@router.get("/pricing/status")
async def get_pricing_status():
    return ok({"service": "ready", "mode": "async-oop"})

@router.get("/pricing/quote")
async def get_pricing_quote(session: AsyncSessionDep, product_id: int, channel: str = "customer"):
    return ok(await _domain(session, ctrl.quote, product_id, channel))

@router.post("/pricing/quote/bulk")
async def post_quote_bulk(body: BulkIn, session: AsyncSessionDep):
    return ok(await _domain(session, ctrl.quote_bulk, body.product_ids, body.channel))

@router.post("/pricing/estimate/custom-cake")
async def post_estimate_custom_cake(weight: str = "1kg", budget_max: float | None = None):
    return ok(ctrl.estimate_cake(weight, budget_max))  # no session

@router.get("/admin/pricing/products")
async def get_pricing_products(session: AsyncSessionDep, _: AdminUser, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    return ok(await _domain(session, ctrl.list_products, page, page_size))

@router.get("/admin/pricing/products/{product_id}")
async def get_products_product_id(product_id: int, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.get_product, product_id))

@router.patch("/admin/pricing/products/{product_id}")
async def patch_products_product_id(product_id: int, body: PricesIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.patch_product, product_id, body.model_dump(exclude_unset=True)))
