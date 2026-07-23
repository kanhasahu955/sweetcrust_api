from __future__ import annotations

from sqlmodel import Session, select

from app.producers.events import emit_order_status
from app.models.commerce import Invoice, Order, OrderItem, Payment
from app.models.enums import OrderStatus
from app.models.ops import BakerySettings
from app.services import integrations as integ
from app.config import get_settings
from package.common.errors import BadRequestError, NotFoundError
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def list_orders(session: Session, status_group: str | None = None):
    stmt = select(Order).order_by(Order.created_at.desc())
    rows = list(session.exec(stmt).all())
    if status_group == "pending":
        rows = [o for o in rows if o.status in (OrderStatus.PLACED, OrderStatus.PAYMENT_RECEIVED)]
    elif status_group == "active":
        rows = [
            o
            for o in rows
            if o.status
            in (
                OrderStatus.ACCEPTED,
                OrderStatus.PREPARING,
                OrderStatus.PACKED,
                OrderStatus.DELIVERY_ASSIGNED,
                OrderStatus.OUT_FOR_DELIVERY,
            )
        ]
    return rows


def order_detail(session: Session, order_id: int) -> dict:
    order = session.get(Order, order_id)
    if not order:
        raise NotFoundError("Order not found")
    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order_id)).all())
    return {"order": order, "items": items}


def update_order_status(
    session: Session,
    order_id: int,
    status: str,
    admin_id: int | None = None,
    note: str | None = None,
    delivery_person_id: int | None = None,
) -> Order:
    order = session.get(Order, order_id)
    if not order:
        raise NotFoundError("Order not found")
    try:
        st = OrderStatus(status)
    except ValueError as exc:
        raise BadRequestError(f"Invalid status: {status}") from exc
    order.status = st
    order.updated_at = utc_now()
    if delivery_person_id is not None:
        order.delivery_person_id = delivery_person_id
    if note:
        order.internal_notes = ((order.internal_notes or "") + f"\n{note}").strip()
    if st == OrderStatus.DELIVERED:
        order.delivered_at = utc_now()
    if st == OrderStatus.CANCELLED:
        order.cancelled_at = utc_now()
        order.cancel_reason = note
    session.add(order)
    session.commit()
    session.refresh(order)
    logger.info("order %s → %s (admin=%s)", order_id, st.value, admin_id)
    emit_order_status(
        order_id,
        {
            "status": st.value,
            "user_id": order.user_id,
            "delivery_person_id": order.delivery_person_id,
        },
    )
    return order


def generate_invoice(session: Session, order: Order) -> Invoice:
    from app.services import invoices as invoice_ops

    invoice = invoice_ops.issue_from_order(session, order)
    logger.info("invoice %s for order %s", invoice.invoice_number, order.id)
    return invoice


def make_invoice(session: Session, order_id: int) -> Invoice:
    detail = order_detail(session, order_id)
    return generate_invoice(session, detail["order"])


def payment_link(session: Session, order_id: int) -> dict:
    detail = order_detail(session, order_id)
    order = detail["order"]
    settings = session.exec(select(BakerySettings)).first()
    app = get_settings()
    upi = (settings.upi_id if settings else None) or app.bakery_upi_id
    out: dict = {
        "order_id": order.id,
        "amount": order.final_amount,
        "upi_link": f"upi://pay?pa={upi}&am={order.final_amount}&tn={order.order_number}",
        "qr_payload": f"upi://pay?pa={upi}&am={order.final_amount}",
        "razorpay_configured": app.razorpay_configured,
    }
    if app.razorpay_configured:
        link = integ.create_payment_link(
            amount_inr=order.final_amount,
            description=f"SweetCrust {order.order_number}",
            reference_id=order.order_number,
            customer_phone=order.customer_phone,
            notes={"order_id": str(order.id), "order_number": order.order_number},
        )
        out["razorpay"] = link
        out["short_url"] = link.get("short_url")
        out["url"] = link.get("short_url")
    return out
