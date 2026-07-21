from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.models.commerce import Order, OrderItem, ReturnRequest
from app.models.enums import OrderStatus, UserRole
from app.models.user import User
from app.services.notifications import notify
from package.common.errors import BadRequestError, NotFoundError
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)

RETURN_STAGES = [
    "submitted",
    "ai_validated",
    "admin_review",
    "approved",
    "rejected",
    "replacement_initiated",
    "refund_initiated",
    "completed",
]


def _assess_return(issue_type: str, evidence_urls: list | None, description: str | None) -> dict:
    # ponytail: stub until AI service owns assess; upgrade = HTTP to ai_service
    return {
        "eligible": True,
        "confidence": 0.7,
        "summary": "Auto-assessed; pending admin review",
        "issue_type": issue_type,
        "evidence_count": len(evidence_urls or []),
        "notes": (description or "")[:200],
    }


def create_return(session: Session, user_id: int, data) -> ReturnRequest:
    order = session.get(Order, data.order_id)
    if not order or order.user_id != user_id:
        raise NotFoundError("Order not found")
    if order.status != OrderStatus.DELIVERED:
        raise BadRequestError("Only delivered orders can be returned")
    if order.delivered_at and order.delivered_at < utc_now() - timedelta(hours=24):
        raise BadRequestError("Return window (24 hours) has expired")

    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
    affected = [i for i in items if i.id in (data.affected_item_ids or [])]
    refund_amount = sum(i.total_price for i in affected) if affected else order.final_amount

    ai = _assess_return(data.issue_type, data.evidence_urls, data.description)

    req = ReturnRequest(
        order_id=order.id,
        user_id=user_id,
        issue_type=data.issue_type,
        solution=data.solution,
        description=data.description,
        affected_item_ids=data.affected_item_ids,
        evidence_urls=data.evidence_urls,
        refund_amount=refund_amount,
        status="ai_validated",
        ai_assessment=ai,
        deadline_at=utc_now() + timedelta(hours=24),
    )
    order.status = OrderStatus.RETURN_REQUESTED
    session.add(req)
    session.add(order)
    session.commit()
    session.refresh(req)
    req.status = "admin_review"
    session.add(req)
    notify(session, user_id, "return", "Return submitted", "We are reviewing your request", {"return_id": req.id}, commit=True)
    admin = session.exec(select(User).where(User.role == UserRole.ADMIN)).first()
    if admin:
        notify(
            session,
            admin.id,
            "return",
            "New return request",
            f"Order {order.order_number}",
            {"return_id": req.id},
            commit=True,
        )
    session.refresh(req)
    logger.info("return=%s order=%s", req.id, order.id)
    return req


def list_returns(session: Session, user_id: int) -> list[ReturnRequest]:
    return list(session.exec(select(ReturnRequest).where(ReturnRequest.user_id == user_id)).all())


def return_detail(session: Session, return_id: int, user_id: int) -> dict:
    req = session.get(ReturnRequest, return_id)
    if not req or req.user_id != user_id:
        return {"message": "not found"}
    return {"return": req, "stages": RETURN_STAGES}
