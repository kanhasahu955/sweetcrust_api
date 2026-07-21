from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.controllers import ratings as ctrl
from app.deps import AsyncSessionDep, CurrentUser
from app.schemas.commerce import OrderRateIn
from package.common.schemas import ok

from app.controllers.rating_async import RatingController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await RatingController(session).call(fn, *args, **kwargs)
router = APIRouter(tags=["rating"])

class ProductReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
    order_id: int | None = None

@router.post("/customer/orders/{order_id}/rate")
async def post_order_id_rate(order_id: int, body: OrderRateIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.rate_order, order_id, user.id, body.rating, body.comment))

@router.get("/customer/products/{product_id}/reviews")
async def get_product_id_reviews(product_id: int, session: AsyncSessionDep, limit: int = 20):
    return ok(await _domain(session, ctrl.list_reviews, product_id, limit))

@router.post("/customer/products/{product_id}/reviews")
async def post_product_id_reviews(product_id: int, body: ProductReviewIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.add_review, user.id, product_id, body.rating, body.comment, body.order_id))
