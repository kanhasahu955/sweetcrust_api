"""Picking / kitchen queue domain."""
from __future__ import annotations
from sqlmodel import Session
from app.models.enums import OrderStatus
from app.repositories import orders as order_repo
from package.common.errors import BadRequestError, NotFoundError
from package.common.utils import utc_now

def _status(v) -> str:
    return v.value if hasattr(v, "value") else str(v)

def queue(session: Session, status: str | None = None) -> dict:
    items = []
    for o in order_repo.list_oldest(session):
        st = _status(o.status)
        if status:
            if st != status:
                continue
        elif st not in {"accepted", "preparing", "packed"}:
            continue
        lines = order_repo.items_for(session, o.id)
        items.append({"order": o, "items": lines, "item_count": sum(int(i.quantity or 0) for i in lines)})
    return {"items": items, "total": len(items)}

def detail(session: Session, order_id: int) -> dict:
    o = order_repo.get(session, order_id)
    if not o:
        raise NotFoundError("Order not found")
    return {"order": o, "items": order_repo.items_for(session, order_id)}

def start(session: Session, order_id: int, actor_id: int):
    o = order_repo.get(session, order_id)
    if not o:
        raise NotFoundError("Order not found")
    if _status(o.status) not in {"accepted", "payment_received", "placed"}:
        raise BadRequestError(f"Cannot start picking from status {_status(o.status)}")
    o.status = OrderStatus.PREPARING
    o.updated_at = utc_now()
    return order_repo.save(session, o)

def pack(session: Session, order_id: int, actor_id: int):
    o = order_repo.get(session, order_id)
    if not o:
        raise NotFoundError("Order not found")
    if _status(o.status) not in {"preparing", "accepted"}:
        raise BadRequestError(f"Cannot pack from status {_status(o.status)}")
    o.status = OrderStatus.PACKED
    o.updated_at = utc_now()
    return order_repo.save(session, o)

def stats(session: Session) -> dict:
    counts = {"accepted": 0, "preparing": 0, "packed": 0}
    for o in order_repo.list_recent(session):
        st = _status(o.status)
        if st in counts:
            counts[st] += 1
    return counts
