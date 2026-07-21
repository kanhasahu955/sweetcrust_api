"""Payment methods, Razorpay flows, customer confirm, invoices."""
from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from app.models.commerce import Invoice, Order, OrderItem, OrderStatusHistory, Payment
from app.models.enums import NotificationType, OrderStatus, PaymentMethod, PaymentStatus
from app.models.ops import BakerySettings, Notification
from app.models.user import User
from app.producers.events import emit_admin_event, emit_order_status
from app.services import razorpay as razorpay_ops
from app.config import get_settings
from package.common.errors import BadRequestError, NotFoundError
from package.common.utils import generate_invoice_number, generate_txn_id, utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def _settings_row(session: Session) -> BakerySettings:
    s = session.exec(select(BakerySettings)).first()
    return s or BakerySettings()


def _notify(session: Session, user_id: int, ntype: str, title: str, body: str, data: dict | None = None) -> None:
    try:
        t = NotificationType(ntype)
    except ValueError:
        t = NotificationType.SYSTEM
    session.add(Notification(user_id=user_id, type=t, title=title, body=body, data=data))


def get_order_payment(session: Session, user_id: int, order_id: int) -> tuple[Order, Payment]:
    order = session.get(Order, order_id)
    if not order or order.user_id != user_id:
        raise NotFoundError("Order not found")
    payment = session.exec(select(Payment).where(Payment.order_id == order_id).order_by(Payment.id.desc())).first()
    if not payment:
        payment = Payment(
            order_id=order.id,
            user_id=user_id,
            amount=order.final_amount,
            method=PaymentMethod.RAZORPAY,
            status=PaymentStatus.PENDING,
            transaction_id=generate_txn_id(),
        )
        session.add(payment)
        session.commit()
        session.refresh(payment)
    return order, payment


def payment_methods(session: Session) -> dict[str, Any]:
    s = session.exec(select(BakerySettings)).first()
    app = get_settings()
    methods = [
        "upi",
        "upi_qr",
        "google_pay",
        "phonepe",
        "paytm",
        "credit_card",
        "debit_card",
        "net_banking",
        "wallet",
    ]
    if not s or s.cod_enabled:
        methods.append("cod")
    methods.append("credit")
    if app.razorpay_configured:
        methods.append("razorpay")
    return {
        "methods": methods,
        "upi_id": (s.upi_id if s else None) or app.bakery_upi_id,
        "razorpay": {
            "configured": app.razorpay_configured,
            "key_id": app.razorpay_key_id if app.razorpay_configured else None,
        },
        "imagekit": {"configured": app.imagekit_configured},
        "secure": True,
    }


def credentials_check() -> dict[str, Any]:
    return {
        "razorpay": razorpay_ops.check_credentials(),
        "imagekit": razorpay_ops.check_imagekit_credentials(),
    }


def generate_invoice(session: Session, order: Order) -> Invoice:
    existing = session.exec(select(Invoice).where(Invoice.order_id == order.id)).first()
    if existing:
        return existing
    settings = _settings_row(session)
    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
    payment = session.exec(select(Payment).where(Payment.order_id == order.id).order_by(Payment.id.desc())).first()
    addr = order.address_snapshot or {}
    invoice = Invoice(
        order_id=order.id,
        invoice_number=generate_invoice_number(),
        bakery_name=settings.bakery_name,
        gstin=settings.gstin,
        customer_name=addr.get("full_name", "Customer"),
        customer_phone=order.customer_phone or addr.get("phone", ""),
        customer_address=", ".join(filter(None, [addr.get("line1"), addr.get("city"), addr.get("pincode")])),
        line_items={
            "items": [
                {"name": i.product_name, "qty": i.quantity, "unit_price": i.unit_price, "total": i.total_price}
                for i in items
            ]
        },
        subtotal=order.subtotal,
        discount=order.discount,
        gst_amount=order.gst_amount,
        delivery_fee=order.delivery_fee,
        grand_total=order.final_amount,
        payment_method=order.payment_method.value if order.payment_method else None,
        transaction_id=payment.transaction_id if payment else None,
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice


def razorpay_create(session: Session, user: User, order_id: int, use_payment_link: bool = True) -> dict[str, Any]:
    order, payment = get_order_payment(session, user.id, order_id)
    if payment.status == PaymentStatus.PAID:
        return {"status": "already_paid", "order_id": order.id, "payment_id": payment.id}

    payment.method = PaymentMethod.RAZORPAY
    payment.status = PaymentStatus.PROCESSING
    order.payment_method = PaymentMethod.RAZORPAY
    notes = {"order_id": str(order.id), "order_number": order.order_number, "user_id": str(user.id)}

    rz_order = razorpay_ops.create_order(
        amount_inr=order.final_amount,
        receipt=order.order_number,
        notes=notes,
    )
    gateway = dict(payment.gateway_response or {})
    gateway["razorpay_order"] = rz_order
    out: dict[str, Any] = {
        "status": "created",
        "order_id": order.id,
        "payment_id": payment.id,
        "amount": order.final_amount,
        **rz_order,
    }

    if use_payment_link:
        link = razorpay_ops.create_payment_link(
            amount_inr=order.final_amount,
            description=f"SweetCrust {order.order_number}",
            reference_id=order.order_number,
            customer_name=user.name,
            customer_phone=user.phone or order.customer_phone,
            notes=notes,
        )
        gateway["payment_link"] = link
        out["payment_link"] = link
        out["short_url"] = link.get("short_url")

    payment.gateway_response = gateway
    payment.updated_at = utc_now()
    order.updated_at = utc_now()
    session.add(payment)
    session.add(order)
    session.commit()
    return out


def razorpay_verify(
    session: Session,
    user: User,
    *,
    order_id: int,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> dict[str, Any]:
    order, payment = get_order_payment(session, user.id, order_id)
    if payment.status == PaymentStatus.PAID:
        return {"status": "success", "order_id": order.id, "already_paid": True}

    ok_sig = razorpay_ops.verify_payment_signature(
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,
    )
    if not ok_sig:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = "Invalid Razorpay signature"
        payment.updated_at = utc_now()
        order.payment_status = PaymentStatus.FAILED
        order.updated_at = utc_now()
        session.add(payment)
        session.add(order)
        session.commit()
        raise BadRequestError("Invalid payment signature")

    payment.method = PaymentMethod.RAZORPAY
    payment.status = PaymentStatus.PAID
    payment.paid_at = utc_now()
    payment.transaction_id = razorpay_payment_id
    gateway = dict(payment.gateway_response or {})
    gateway["verify"] = {
        "order_id": order_id,
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "razorpay_signature": razorpay_signature,
    }
    payment.gateway_response = gateway
    payment.updated_at = utc_now()
    order.payment_status = PaymentStatus.PAID
    order.payment_method = PaymentMethod.RAZORPAY
    order.status = OrderStatus.PAYMENT_RECEIVED
    order.updated_at = utc_now()
    session.add(payment)
    session.add(order)
    session.add(
        OrderStatusHistory(
            order_id=order.id, status=OrderStatus.PAYMENT_RECEIVED, note="Razorpay payment verified"
        )
    )
    invoice = generate_invoice(session, order)
    session.commit()
    emit_order_status(
        order.id,
        {
            "status": OrderStatus.PAYMENT_RECEIVED.value,
            "payment_status": PaymentStatus.PAID.value,
            "source": "razorpay_verify",
        },
    )
    emit_admin_event(
        "order_paid",
        {
            "order_id": order.id,
            "order_number": order.order_number,
            "amount": float(order.final_amount or 0),
            "method": "razorpay",
            "source": "verify",
        },
    )
    return {"status": "success", "order_id": order.id, "payment": payment, "invoice": invoice}


def razorpay_webhook(session: Session, body: bytes, signature: str) -> dict[str, Any]:
    s = get_settings()
    if s.razorpay_webhook_secret and not razorpay_ops.verify_webhook_signature(body, signature):
        raise BadRequestError("Invalid webhook signature")

    try:
        payload = json.loads(body.decode() or "{}")
    except json.JSONDecodeError as exc:
        raise BadRequestError("Invalid JSON") from exc

    event = payload.get("event")
    entity = (payload.get("payload") or {}).get("payment", {}).get("entity") or {}
    notes = entity.get("notes") or {}
    order_id = notes.get("order_id")
    payment_id = entity.get("id")
    if not order_id or event not in ("payment.captured", "payment.authorized"):
        return {"ok": True, "ignored": True, "event": event}

    order = session.get(Order, int(order_id))
    if not order:
        return {"ok": True, "ignored": True, "detail": "order missing"}
    payment = session.exec(select(Payment).where(Payment.order_id == order.id).order_by(Payment.id.desc())).first()
    if not payment:
        return {"ok": True, "ignored": True, "detail": "payment missing"}
    if payment.status == PaymentStatus.PAID:
        return {"ok": True, "already_paid": True}

    payment.method = PaymentMethod.RAZORPAY
    payment.status = PaymentStatus.PAID
    payment.paid_at = utc_now()
    if payment_id:
        payment.transaction_id = payment_id
    gateway = dict(payment.gateway_response or {})
    gateway["webhook"] = {"event": event, "payment_id": payment_id}
    payment.gateway_response = gateway
    payment.updated_at = utc_now()
    order.payment_status = PaymentStatus.PAID
    order.payment_method = PaymentMethod.RAZORPAY
    order.updated_at = utc_now()
    if order.status == OrderStatus.PLACED:
        order.status = OrderStatus.PAYMENT_RECEIVED
        session.add(
            OrderStatusHistory(
                order_id=order.id, status=OrderStatus.PAYMENT_RECEIVED, note="Razorpay webhook"
            )
        )
    session.add(payment)
    session.add(order)
    session.commit()
    emit_order_status(
        order.id,
        {
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
            "payment_status": PaymentStatus.PAID.value,
            "source": "razorpay_webhook",
        },
    )
    emit_admin_event(
        "order_paid",
        {
            "order_id": order.id,
            "order_number": order.order_number,
            "amount": float(order.final_amount or 0),
            "method": "razorpay",
            "source": "webhook",
            "razorpay_payment_id": payment_id,
        },
    )
    return {"ok": True, "order_id": order.id}


def process_payment(
    session: Session,
    user_id: int,
    order_id: int,
    method: str,
    upi_id: str | None,
    fail: bool = False,
) -> dict[str, Any]:
    order = session.get(Order, order_id)
    if not order or order.user_id != user_id:
        raise NotFoundError("Order not found")
    payment = session.exec(select(Payment).where(Payment.order_id == order_id).order_by(Payment.id.desc())).first()
    if not payment:
        raise NotFoundError("Payment not found")
    try:
        payment.method = PaymentMethod(method)
    except ValueError as exc:
        raise BadRequestError(f"Invalid payment method: {method}") from exc
    payment.upi_id = upi_id
    payment.status = PaymentStatus.PROCESSING
    payment.updated_at = utc_now()
    session.add(payment)
    session.commit()

    if fail:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = "Payment declined by bank / UPI"
        payment.updated_at = utc_now()
        order.payment_status = PaymentStatus.FAILED
        order.updated_at = utc_now()
        session.add(payment)
        session.add(order)
        session.commit()
        return {"status": "failed", "order_id": order.id, "payment": payment, "retry": True}

    payment.status = PaymentStatus.PAID
    payment.paid_at = utc_now()
    payment.updated_at = utc_now()
    order.payment_status = PaymentStatus.PAID
    order.payment_method = payment.method
    order.status = OrderStatus.PAYMENT_RECEIVED
    order.updated_at = utc_now()
    session.add(OrderStatusHistory(order_id=order.id, status=OrderStatus.PAYMENT_RECEIVED, note="Payment received"))
    session.add(payment)
    session.add(order)
    _notify(
        session,
        user_id,
        "payment",
        "Payment successful",
        f"₹{order.final_amount:.0f} paid for {order.order_number}",
        {"order_id": order.id},
    )
    invoice = generate_invoice(session, order)
    session.commit()
    logger.info("payment confirmed order=%s method=%s", order.id, method)
    return {"status": "success", "order_id": order.id, "payment": payment, "invoice": invoice}
