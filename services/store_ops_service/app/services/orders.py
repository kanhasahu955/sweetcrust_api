from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.producers.events import emit_order_status, emit_user_event
from app.models.commerce import Invoice, Order, OrderItem
from app.models.enums import OrderStatus
from app.models.ops import BakerySettings, DeliveryPerson, DeliveryTracking
from app.services import integrations as integ
from app.config import get_settings
from package.common.errors import BadRequestError, NotFoundError
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)

OFFER_TTL_SEC = 45


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
                OrderStatus.DELIVERY_OFFERED,
                OrderStatus.DELIVERY_ASSIGNED,
                OrderStatus.PICKED_UP,
                OrderStatus.OUT_FOR_DELIVERY,
                OrderStatus.NEAR_LOCATION,
            )
        ]
    return rows


def order_detail(session: Session, order_id: int) -> dict:
    order = session.get(Order, order_id)
    if not order:
        raise NotFoundError("Order not found")
    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order_id)).all())
    return {"order": order, "items": items}


def _bakery(session: Session) -> BakerySettings:
    return session.exec(select(BakerySettings)).first() or BakerySettings()


def _upsert_tracking(session: Session, order: Order, delivery_person_id: int) -> None:
    tracking = session.exec(select(DeliveryTracking).where(DeliveryTracking.order_id == order.id)).first()
    addr = order.address_snapshot or {}
    settings = _bakery(session)
    cust_lat = addr.get("latitude") or addr.get("lat")
    cust_lng = addr.get("longitude") or addr.get("lng")
    if not tracking:
        session.add(
            DeliveryTracking(
                order_id=order.id,
                delivery_person_id=delivery_person_id,
                bakery_lat=settings.latitude,
                bakery_lng=settings.longitude,
                customer_lat=float(cust_lat) if cust_lat is not None else None,
                customer_lng=float(cust_lng) if cust_lng is not None else None,
                rider_lat=settings.latitude,
                rider_lng=settings.longitude,
                eta_minutes=35,
                distance_km=4.2,
            )
        )
    else:
        tracking.delivery_person_id = delivery_person_id
        tracking.updated_at = utc_now()
        if cust_lat is not None:
            tracking.customer_lat = float(cust_lat)
        if cust_lng is not None:
            tracking.customer_lng = float(cust_lng)
        session.add(tracking)


def _rider_user_id(session: Session, delivery_person_id: int | None) -> int | None:
    if not delivery_person_id:
        return None
    person = session.get(DeliveryPerson, delivery_person_id)
    return person.user_id if person and person.user_id else None


def _notify_rider(
    session: Session,
    order: Order,
    *,
    kind: str,
    status: str,
) -> None:
    rider_uid = _rider_user_id(session, order.delivery_person_id)
    payload = {
        "status": status,
        "user_id": order.user_id,
        "delivery_person_id": order.delivery_person_id,
        "order_number": order.order_number,
        "rider_user_id": rider_uid,
    }
    if getattr(order, "offer_expires_at", None):
        payload["expires_at"] = order.offer_expires_at.isoformat()
    emit_order_status(order.id, payload)
    if rider_uid:
        emit_user_event(
            rider_uid,
            kind,
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "status": status,
                "expires_at": payload.get("expires_at"),
                "delivery_person_id": order.delivery_person_id,
            },
        )


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
        person = session.get(DeliveryPerson, delivery_person_id)
        if not person:
            raise NotFoundError("Delivery person not found")
        order.delivery_person_id = delivery_person_id
        _upsert_tracking(session, order, delivery_person_id)
    if st == OrderStatus.DELIVERY_ASSIGNED:
        order.offer_expires_at = None
        if order.delivery_person_id:
            _upsert_tracking(session, order, order.delivery_person_id)
    if st == OrderStatus.DELIVERY_OFFERED:
        order.offer_expires_at = utc_now() + timedelta(seconds=OFFER_TTL_SEC)
        if order.delivery_person_id:
            _upsert_tracking(session, order, order.delivery_person_id)
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

    kind = "delivery_updated"
    if st == OrderStatus.DELIVERY_ASSIGNED and delivery_person_id is not None:
        kind = "delivery_job"
    elif st == OrderStatus.DELIVERY_OFFERED:
        kind = "delivery_offer"
    elif st == OrderStatus.CANCELLED:
        kind = "delivery_cancelled"
    _notify_rider(session, order, kind=kind, status=st.value)
    return order


def offer_delivery(session: Session, order_id: int, delivery_person_id: int, admin_id: int | None = None) -> Order:
    """1B — soft offer with 45s accept window."""
    return update_order_status(
        session,
        order_id,
        OrderStatus.DELIVERY_OFFERED.value,
        admin_id,
        note="Offered to rider",
        delivery_person_id=delivery_person_id,
    )


def assign_delivery(session: Session, order_id: int, delivery_person_id: int, admin_id: int | None = None) -> Order:
    """1A — forced assign; rider must run it."""
    return update_order_status(
        session,
        order_id,
        OrderStatus.DELIVERY_ASSIGNED.value,
        admin_id,
        note="Assigned to rider",
        delivery_person_id=delivery_person_id,
    )


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
        out["razorpay_payment_link"] = link
    return out
