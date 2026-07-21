"""Customer payment aliases — gateway /api/v1/customer/payments/*."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import CurrentUser, SessionDep
from app.services import payments as pay_ops
from app.schemas.payments import PaymentConfirmIn
from package.common.schemas import ok

router = APIRouter(prefix="/customer/payments", tags=["customer-payments"])


@router.post("/confirm")
def confirm(body: PaymentConfirmIn, session: SessionDep, user: CurrentUser):
    return ok(
        pay_ops.process_payment(
            session,
            user.id,
            body.order_id,
            body.method,
            body.upi_id,
            body.simulate_failure,
        )
    )


@router.get("/methods")
def methods(session: SessionDep):
    return ok(pay_ops.payment_methods(session))
