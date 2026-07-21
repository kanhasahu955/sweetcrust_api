"""Shared down-payment rules for COD/UPI partial billing."""
from __future__ import annotations

from package.common.errors import BadRequestError

# First payment must cover this share of the bill; remainder may be paid later.
MIN_FIRST_PAY_RATIO = 0.80


def min_first_pay(total: float) -> float:
    return round(float(total) * MIN_FIRST_PAY_RATIO, 2)


def assert_first_or_partial_pay(*, total: float, already_paid: float, pay: float) -> None:
    """Validate a payment against 80% first-pay rule."""
    total = round(float(total), 2)
    already = round(float(already_paid or 0), 2)
    pay = round(float(pay), 2)
    due = round(total - already, 2)
    if pay <= 0:
        raise BadRequestError("Pay amount must be > 0")
    if pay > due + 0.01:
        raise BadRequestError(f"Pay amount must be at most ₹{due:.2f}")
    if already <= 0.001:
        need = min_first_pay(total)
        if pay + 0.01 < need and pay + 0.01 < due:
            raise BadRequestError(
                f"First payment must be at least 80% (₹{need:.2f}). Rest can be paid later."
            )
