from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.controllers import promotions as ctrl
from app.deps import AsyncSessionDep, AdminUser, CurrentUser
from app.schemas.commerce import CouponApplyIn
from package.common.schemas import ok

from app.controllers.promotion_async import PromotionController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await PromotionController(session).call(fn, *args, **kwargs)
router = APIRouter(tags=["promotion"])

class CouponIn(BaseModel):
    code: str
    title: str
    description: str | None = None
    coupon_type: str = "percentage"
    value: float = 0
    min_order_amount: float = 0
    max_discount: float | None = None
    is_active: bool = True

class ValidateIn(BaseModel):
    code: str
    subtotal: float = Field(0, ge=0)

@router.post("/customer/cart/coupon")
async def post_cart_coupon(body: CouponApplyIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.apply_coupon, user.id, body.code))

@router.post("/customer/coupons/validate")
async def post_coupons_validate(body: ValidateIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.validate, body.code, body.subtotal))

@router.get("/admin/coupons")
async def get_admin_coupons(session: AsyncSessionDep, _: AdminUser, active_only: bool = False):
    return ok(await _domain(session, ctrl.list_coupons, active_only=active_only))

@router.post("/admin/coupons")
async def post_admin_coupons(body: CouponIn, session: AsyncSessionDep, _: AdminUser):
    return ok(await _domain(session, ctrl.create_coupon, body.model_dump()))

@router.patch("/admin/coupons/{coupon_id}")
async def patch_coupons_coupon_id(coupon_id: int, session: AsyncSessionDep, _: AdminUser, is_active: bool = True):
    return ok(await _domain(session, ctrl.set_active, coupon_id, is_active))
