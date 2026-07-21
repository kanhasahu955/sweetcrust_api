from sqlmodel import Session, select

from app.models.enums import NotificationType
from app.models.ops import Notification


def notify(
    session: Session,
    user_id: int,
    ntype: str,
    title: str,
    body: str,
    data: dict | None = None,
    commit: bool = False,
) -> Notification:
    try:
        t = NotificationType(ntype)
    except ValueError:
        t = NotificationType.SYSTEM
    n = Notification(user_id=user_id, type=t, title=title, body=body, data=data)
    session.add(n)
    if commit:
        session.commit()
        session.refresh(n)
    return n


def list_notifications(session: Session, user_id: int, unread_only: bool = False) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)  # noqa: E712
    return list(session.exec(stmt.limit(100)).all())


def mark_read(session: Session, user_id: int, notification_id: int | None = None) -> dict:
    if notification_id:
        n = session.get(Notification, notification_id)
        if n and n.user_id == user_id:
            n.is_read = True
            session.add(n)
    else:
        for n in session.exec(select(Notification).where(Notification.user_id == user_id, Notification.is_read == False)).all():  # noqa: E712
            n.is_read = True
            session.add(n)
    session.commit()
    return {"message": "ok"}
