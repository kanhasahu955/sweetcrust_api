"""Dispatch HTTP adapters."""
from __future__ import annotations

from sqlmodel import Session

from app.services import delivery as delivery_ops
from app.services import orders as order_ops


def live(session: Session):
    return delivery_ops.live(session)


def assign(session: Session, order_id: int, delivery_person_id: int, actor_id: int):
    return order_ops.update_order_status(
        session,
        order_id,
        "delivery_assigned",
        admin_id=actor_id,
        delivery_person_id=delivery_person_id,
    )


def update_status(
    session: Session,
    order_id: int,
    status: str,
    actor_id: int,
    note: str | None = None,
    delivery_person_id: int | None = None,
):
    return order_ops.update_order_status(
        session,
        order_id,
        status,
        admin_id=actor_id,
        note=note,
        delivery_person_id=delivery_person_id,
    )
