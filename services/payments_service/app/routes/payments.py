"""Razorpay create / verify / webhook + payment methods."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.deps import CurrentUser, SessionDep
from app.services import payments as pay_ops
from app.schemas.payments import RazorpayCreateIn, RazorpayVerifyIn
from package.common.schemas import ok

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/methods")
def payment_methods(session: SessionDep):
    return ok(pay_ops.payment_methods(session))


@router.get("/credentials/check")
def credentials_check(_: CurrentUser):
    return ok(pay_ops.credentials_check())


@router.post("/razorpay/create")
def razorpay_create(body: RazorpayCreateIn, session: SessionDep, user: CurrentUser):
    return ok(pay_ops.razorpay_create(session, user, body.order_id, body.use_payment_link))


@router.post("/razorpay/verify")
def razorpay_verify(body: RazorpayVerifyIn, session: SessionDep, user: CurrentUser):
    return ok(
        pay_ops.razorpay_verify(
            session,
            user,
            order_id=body.order_id,
            razorpay_order_id=body.razorpay_order_id,
            razorpay_payment_id=body.razorpay_payment_id,
            razorpay_signature=body.razorpay_signature,
        )
    )


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, session: SessionDep):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    return ok(pay_ops.razorpay_webhook(session, body, signature))
