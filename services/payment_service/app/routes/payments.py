"""Razorpay create / verify / webhook + payment methods."""
from __future__ import annotations
from fastapi import APIRouter, Request
from app.controllers import payments as ctrl
from app.deps import CurrentUser, AsyncSessionDep
from app.schemas.payments import RazorpayCreateIn, RazorpayVerifyIn
from package.common.schemas import ok
from app.controllers.payment_async import PaymentController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await PaymentController(session).call(fn, *args, **kwargs)

router = APIRouter(prefix='/payments', tags=['payments'])

@router.get('/methods')
async def payment_methods(session: AsyncSessionDep):
    return ok(await _domain(session, ctrl.payment_methods))

@router.get('/credentials/check')
def credentials_check(_: CurrentUser):
    return ok(ctrl.credentials_check())

@router.post('/razorpay/create')
async def razorpay_create(body: RazorpayCreateIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.razorpay_create, user, body.order_id, body.use_payment_link))

@router.post('/razorpay/verify')
async def razorpay_verify(body: RazorpayVerifyIn, session: AsyncSessionDep, user: CurrentUser):
    return ok(await _domain(session, ctrl.razorpay_verify, user, order_id=body.order_id, razorpay_order_id=body.razorpay_order_id, razorpay_payment_id=body.razorpay_payment_id, razorpay_signature=body.razorpay_signature))

@router.post('/webhooks/razorpay')
async def razorpay_webhook(request: Request, session: AsyncSessionDep):
    body = await request.body()
    signature = request.headers.get('X-Razorpay-Signature', '')
    return ok(await _domain(session, ctrl.razorpay_webhook, body, signature))
