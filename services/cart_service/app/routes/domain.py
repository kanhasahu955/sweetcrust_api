from __future__ import annotations
from fastapi import APIRouter
from app.controllers import cart as ctrl
from app.deps import AsyncSessionDep, CurrentUser
from app.schemas.commerce import CartItemIn, CartItemUpdateIn, CouponApplyIn
from package.common.schemas import ok

from app.controllers.cart_async import CartController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await CartController(session).call(fn, *args, **kwargs)
router = APIRouter(prefix="/customer", tags=["cart"])

@router.get("/cart")
async def get_cart(session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.get_cart, user.id))

@router.post("/cart/items")
async def post_cart_items(body: CartItemIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.add_item, user.id, body.product_id, body.quantity, body.variant, body.flavor, body.is_eggless))

@router.patch("/cart/items/{item_id}")
async def patch_items_item_id(item_id: int, body: CartItemUpdateIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.patch_item, user.id, item_id, body.quantity, body.saved_for_later))

@router.delete("/cart/items/{item_id}")
async def delete_items_item_id(item_id: int, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.remove_item, user.id, item_id))

@router.post("/cart/coupon")
async def post_cart_coupon(body: CouponApplyIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.apply_coupon, user.id, body.code))
