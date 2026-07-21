"""Notification persistence."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Notification

def list_for_user(session: Session, user_id: int, unread_only: bool = False) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
    rows = list(session.exec(stmt).all())
    if unread_only:
        rows = [n for n in rows if not n.is_read]
    return rows

def get(session: Session, notification_id: int) -> Notification | None:
    return session.get(Notification, notification_id)

def save(session: Session, n: Notification) -> Notification:
    session.add(n)
    session.commit()
    session.refresh(n)
    return n
