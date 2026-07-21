from __future__ import annotations
from fastapi import APIRouter
from app.controllers import checkout as ctrl
from app.deps import AsyncSessionDep, CurrentUser
from app.schemas.commerce import CheckoutIn
from package.common.schemas import ok

from app.controllers.checkout_async import CheckoutController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await CheckoutController(session).call(fn, *args, **kwargs)
router = APIRouter(prefix="/customer", tags=["checkout"])

@router.post("/checkout")
async def post_checkout(body: CheckoutIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.checkout, user.id, body))
