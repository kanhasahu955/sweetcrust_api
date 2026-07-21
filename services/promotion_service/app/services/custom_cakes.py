from __future__ import annotations

from sqlmodel import Session, select

from app.models.commerce import CustomCakeRequest
from app.models.enums import CustomCakeStatus, UserRole
from app.models.user import User
from app.services.notifications import notify
from package.logger import get_logger

logger = get_logger(__name__)


def estimate_price(weight: str, budget_max: float | None) -> float:
    mapping = {"0.5 kg": 549, "1 kg": 899, "1.5 kg": 1299, "2 kg": 1699, "3 kg": 2499}
    base = mapping.get(weight, 999)
    if budget_max:
        return min(base, budget_max)
    return float(base)


def create_request(session: Session, user_id: int, data) -> CustomCakeRequest:
    est = estimate_price(data.weight, data.budget_max)
    req = CustomCakeRequest(
        user_id=user_id,
        **data.model_dump(),
        estimated_price=est,
        ai_suggestions=[
            {"theme": "Pastel floral with gold leaf", "extra": 150},
            {"theme": "Cartoon topper + drip", "extra": 200},
            {"theme": "Minimal elegant script", "extra": 0},
        ],
        status=CustomCakeStatus.REQUESTED,
    )
    session.add(req)
    session.commit()
    session.refresh(req)
    admin = session.exec(select(User).where(User.role == UserRole.ADMIN)).first()
    if admin:
        notify(
            session,
            admin.id,
            "custom_cake",
            "Custom cake request",
            f"{data.occasion} · {data.flavor}",
            {"id": req.id},
            commit=True,
        )
    notify(
        session,
        user_id,
        "custom_cake",
        "Request received",
        "We'll share a quotation soon",
        {"id": req.id},
        commit=True,
    )
    logger.info("custom cake request=%s user=%s", req.id, user_id)
    return req


def list_requests(session: Session, user_id: int) -> list[CustomCakeRequest]:
    return list(session.exec(select(CustomCakeRequest).where(CustomCakeRequest.user_id == user_id)).all())
