"""Customer payment aliases — gateway /api/v1/customer/payments/*."""
from __future__ import annotations
from fastapi import APIRouter
from app.controllers import payments as ctrl
from app.deps import CurrentUser, AsyncSessionDep
from app.schemas.payments import PaymentConfirmIn
from package.common.schemas import ok
from app.controllers.payment_async import PaymentController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await PaymentController(session).call(fn, *args, **kwargs)

router = APIRouter(prefix='/customer/payments', tags=['customer-payments'])

@router.post('/confirm')
async def confirm(body: PaymentConfirmIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.confirm, user.id, body.order_id, body.method, body.upi_id, body.simulate_failure))

@router.get('/methods')
async def methods(session: AsyncSessionDep):
    return ok(await _domain(session, ctrl.payment_methods))
