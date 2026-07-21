from __future__ import annotations

from typing import Optional

from pydantic import Field

from package.common.schemas import APIModel


class RazorpayCreateIn(APIModel):
    order_id: int
    use_payment_link: bool = True


class RazorpayVerifyIn(APIModel):
    order_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str = Field(min_length=10)


class PaymentConfirmIn(APIModel):
    order_id: int
    method: str
    upi_id: Optional[str] = None
    simulate_failure: bool = False
