"""Payment HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import payments as pay_ops

def payment_methods(session: Session):
    return pay_ops.payment_methods(session)

def credentials_check():
    return pay_ops.credentials_check()

def confirm(session: Session, user_id: int, order_id: int, method: str, upi_id=None, simulate_failure=False):
    return pay_ops.process_payment(session, user_id, order_id, method, upi_id, simulate_failure)

def razorpay_create(session: Session, user, order_id: int, use_payment_link: bool = False):
    return pay_ops.razorpay_create(session, user, order_id, use_payment_link)

def razorpay_verify(session: Session, user, **kwargs):
    return pay_ops.razorpay_verify(session, user, **kwargs)

def razorpay_webhook(session: Session, body: bytes, signature: str):
    return pay_ops.razorpay_webhook(session, body, signature)
