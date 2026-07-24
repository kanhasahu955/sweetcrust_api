"""Authenticated delivery-rider operations."""
from __future__ import annotations

from sqlmodel import Session, select

from app.producers.events import emit_admin_event, emit_delivery_location, emit_order_status, emit_user_event
from app.models.commerce import Order, OrderItem, Payment
from app.models.enums import OrderStatus, PaymentStatus
from app.models.ops import DeliveryPerson, DeliveryTracking
from app.models.user import User
from package.common.errors import BadRequestError, ForbiddenError, NotFoundError
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)

RIDER_STATUS_STEPS = ("picked_up", "out_for_delivery", "near_location")


def _person_for_user(session: Session, user: User) -> DeliveryPerson:
    person = session.exec(select(DeliveryPerson).where(DeliveryPerson.user_id == user.id)).first()
    if not person:
        person = session.exec(select(DeliveryPerson).where(DeliveryPerson.phone == user.phone)).first()
        if person:
            person.user_id = user.id
            session.add(person)
            session.commit()
            session.refresh(person)
    if not person:
        # Delivery-role users can log in before admin creates a rider row — provision one.
        person = DeliveryPerson(
            user_id=user.id,
            name=(user.name or "Rider").strip() or "Rider",
            phone=user.phone,
            vehicle_number="TBD",
            is_available=True,
        )
        session.add(person)
        session.commit()
        session.refresh(person)
        logger.info("auto-created delivery_person id=%s for user_id=%s", person.id, user.id)
    return person


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "phone": user.phone,
        "name": user.name,
        "email": user.email,
        "email_verified": bool(getattr(user, "email_verified", False)),
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "language": user.language,
        "avatar_url": user.avatar_url,
        "is_guest": user.is_guest,
        "is_online": getattr(user, "is_online", False),
        "last_seen_at": user.last_seen_at.isoformat() if getattr(user, "last_seen_at", None) else None,
    }


def get_delivery_profile(session: Session, user: User) -> dict:
    person = session.exec(select(DeliveryPerson).where(DeliveryPerson.user_id == user.id)).first()
    if not person:
        person = session.exec(select(DeliveryPerson).where(DeliveryPerson.phone == user.phone)).first()
        if person and not person.user_id:
            person.user_id = user.id
            session.add(person)
            session.commit()
            session.refresh(person)
    return {
        "user": _user_dict(user),
        "delivery_person": (
            {
                "id": person.id,
                "name": person.name,
                "phone": person.phone,
                "vehicle_number": person.vehicle_number,
                "is_available": person.is_available,
                "current_lat": person.current_lat,
                "current_lng": person.current_lng,
                "photo_url": person.photo_url,
            }
            if person
            else None
        ),
    }


def order_detail(session: Session, order_id: int) -> dict:
    order = session.get(Order, order_id)
    if not order:
        raise NotFoundError("Order not found")
    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
    payment = session.exec(select(Payment).where(Payment.order_id == order.id).order_by(Payment.id.desc())).first()
    tracking = session.exec(select(DeliveryTracking).where(DeliveryTracking.order_id == order.id)).first()
    delivery_person = session.get(DeliveryPerson, order.delivery_person_id) if order.delivery_person_id else None
    return {
        "order": order,
        "items": items,
        "payment": payment,
        "tracking": tracking,
        "delivery_person": delivery_person,
    }


def _clear_expired_offer(session: Session, order: Order) -> bool:
    """Lazy timeout for delivery_offered — returns True if cleared."""
    if order.status != OrderStatus.DELIVERY_OFFERED:
        return False
    exp = getattr(order, "offer_expires_at", None)
    if exp and exp > utc_now():
        return False
    rider_uid = None
    if order.delivery_person_id:
        person = session.get(DeliveryPerson, order.delivery_person_id)
        rider_uid = person.user_id if person else None
    order_id = order.id
    order_number = order.order_number
    person_id = order.delivery_person_id
    order.status = OrderStatus.PACKED
    order.delivery_person_id = None
    order.offer_expires_at = None
    order.updated_at = utc_now()
    order.internal_notes = ((order.internal_notes or "") + "\nOffer expired").strip()
    session.add(order)
    session.commit()
    emit_admin_event(
        "delivery_offer_expired",
        {"order_id": order_id, "order_number": order_number, "delivery_person_id": person_id},
    )
    if rider_uid:
        emit_user_event(rider_uid, "delivery_cancelled", {"order_id": order_id, "reason": "expired"})
    emit_order_status(
        order_id,
        {"status": OrderStatus.PACKED.value, "user_id": order.user_id, "rider_user_id": rider_uid},
    )
    return True


def my_orders(session: Session, user: User) -> list[dict]:
    person = _person_for_user(session, user)
    orders = list(
        session.exec(
            select(Order)
            .where(Order.delivery_person_id == person.id)
            .order_by(Order.created_at.desc())
            .limit(50)
        ).all()
    )
    out = []
    for o in orders:
        if _clear_expired_offer(session, o):
            continue
        out.append(order_detail(session, o.id))
    return out


def update_availability(session: Session, user: User, is_available: bool) -> dict:
    person = _person_for_user(session, user)
    person.is_available = is_available
    session.add(person)
    session.commit()
    return {"is_available": person.is_available}


def update_location(
    session: Session,
    user: User,
    *,
    lat: float,
    lng: float,
    order_id: int | None = None,
    eta_minutes: int | None = None,
    distance_km: float | None = None,
) -> dict:
    person = _person_for_user(session, user)
    person.current_lat = lat
    person.current_lng = lng
    session.add(person)

    track = None
    if order_id:
        order = session.get(Order, order_id)
        if not order or order.delivery_person_id != person.id:
            raise ForbiddenError("Order not assigned to you")
        track = session.exec(select(DeliveryTracking).where(DeliveryTracking.order_id == order_id)).first()
        if track:
            track.rider_lat = lat
            track.rider_lng = lng
            track.updated_at = utc_now()
            if eta_minutes is not None:
                track.eta_minutes = eta_minutes
            if distance_km is not None:
                track.distance_km = distance_km
            session.add(track)

    session.commit()
    if order_id:
        emit_delivery_location(
            order_id,
            {
                "lat": lat,
                "lng": lng,
                "eta_minutes": track.eta_minutes if track else eta_minutes,
                "distance_km": track.distance_km if track else distance_km,
                "delivery_person_id": person.id,
            },
        )
    return {
        "delivery_person_id": person.id,
        "lat": lat,
        "lng": lng,
        "order_id": order_id,
        "eta_minutes": track.eta_minutes if track else eta_minutes,
        "distance_km": track.distance_km if track else distance_km,
    }


def accept_order(session: Session, user: User, order_id: int) -> Order:
    person = _person_for_user(session, user)
    order = session.get(Order, order_id)
    if not order or order.delivery_person_id != person.id:
        raise ForbiddenError("Order not offered to you")
    if _clear_expired_offer(session, order):
        raise BadRequestError("Offer expired")
    order = session.get(Order, order_id)
    if not order or order.status != OrderStatus.DELIVERY_OFFERED:
        raise BadRequestError("Order is not an open offer")
    order.status = OrderStatus.DELIVERY_ASSIGNED
    order.offer_expires_at = None
    order.updated_at = utc_now()
    order.internal_notes = ((order.internal_notes or "") + "\nAccepted by rider").strip()
    session.add(order)
    session.commit()
    session.refresh(order)
    emit_order_status(
        order_id,
        {
            "status": order.status.value,
            "user_id": order.user_id,
            "delivery_person_id": order.delivery_person_id,
            "rider_user_id": user.id,
        },
    )
    emit_user_event(
        user.id,
        "delivery_job",
        {"order_id": order.id, "order_number": order.order_number, "status": order.status.value},
    )
    emit_admin_event("delivery_accepted", {"order_id": order.id, "delivery_person_id": person.id})
    return order


def reject_order(session: Session, user: User, order_id: int) -> dict:
    person = _person_for_user(session, user)
    order = session.get(Order, order_id)
    if not order or order.delivery_person_id != person.id:
        raise ForbiddenError("Order not offered to you")
    if order.status != OrderStatus.DELIVERY_OFFERED:
        raise BadRequestError("Only open offers can be rejected")
    order.status = OrderStatus.PACKED
    order.delivery_person_id = None
    order.offer_expires_at = None
    order.updated_at = utc_now()
    order.internal_notes = ((order.internal_notes or "") + "\nRejected by rider").strip()
    session.add(order)
    session.commit()
    emit_admin_event(
        "delivery_rejected",
        {"order_id": order_id, "delivery_person_id": person.id, "order_number": order.order_number},
    )
    emit_user_event(user.id, "delivery_cancelled", {"order_id": order_id, "reason": "rejected"})
    emit_order_status(
        order_id,
        {"status": OrderStatus.PACKED.value, "user_id": order.user_id, "rider_user_id": user.id},
    )
    return {"ok": True, "order_id": order_id}


def update_order_status(session: Session, user: User, order_id: int, status: str) -> Order:
    person = _person_for_user(session, user)
    order = session.get(Order, order_id)
    if not order or order.delivery_person_id != person.id:
        raise ForbiddenError("Order not assigned to you")
    if order.status == OrderStatus.DELIVERY_OFFERED:
        raise BadRequestError("Accept the offer before updating trip status")

    key = str(status or "").strip().lower()
    if key == "reached_bakery":
        order.internal_notes = ((order.internal_notes or "") + "\nReached bakery").strip()
        order.updated_at = utc_now()
        session.add(order)
        session.commit()
        session.refresh(order)
        emit_user_event(
            user.id,
            "delivery_updated",
            {"order_id": order.id, "status": "reached_bakery"},
        )
        emit_order_status(
            order_id,
            {
                "status": order.status.value,
                "step": "reached_bakery",
                "user_id": order.user_id,
                "delivery_person_id": order.delivery_person_id,
                "rider_user_id": user.id,
            },
        )
        return order

    if key not in RIDER_STATUS_STEPS:
        raise BadRequestError(f"Invalid status. Allowed: reached_bakery, {', '.join(RIDER_STATUS_STEPS)}")
    try:
        st = OrderStatus(key)
    except ValueError as exc:
        raise BadRequestError(f"Invalid status: {key}") from exc

    order.status = st
    order.updated_at = utc_now()
    session.add(order)
    session.commit()
    session.refresh(order)
    emit_order_status(
        order_id,
        {
            "status": st.value,
            "user_id": order.user_id,
            "delivery_person_id": order.delivery_person_id,
            "rider_user_id": user.id,
        },
    )
    return order


def mark_delivered(session: Session, user: User, order_id: int) -> Order:
    person = _person_for_user(session, user)
    order = session.get(Order, order_id)
    if not order or order.delivery_person_id != person.id:
        raise ForbiddenError("Order not assigned to you")
    if order.status == OrderStatus.DELIVERY_OFFERED:
        raise BadRequestError("Accept the offer before delivering")

    st = OrderStatus.DELIVERED
    order.status = st
    order.updated_at = utc_now()
    order.delivered_at = utc_now()
    order.payment_status = PaymentStatus.PAID
    note = "Delivered by rider"
    order.internal_notes = ((order.internal_notes or "") + f"\n{note}").strip()

    cust = session.get(User, order.user_id)
    if cust:
        cust.total_spent += order.final_amount
        cust.last_order_at = utc_now()
        session.add(cust)

    session.add(order)
    session.commit()
    session.refresh(order)
    logger.info("order %s → delivered (rider=%s)", order_id, user.id)
    emit_order_status(
        order_id,
        {
            "status": st.value,
            "user_id": order.user_id,
            "delivery_person_id": order.delivery_person_id,
            "rider_user_id": user.id,
        },
    )
    return order
