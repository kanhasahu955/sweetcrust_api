from __future__ import annotations

from sqlmodel import Session, select

from app.models.user import Address, User
from app.services.geo import assert_within_radius


def list_addresses(session: Session, user_id: int) -> list[Address]:
    return list(session.exec(select(Address).where(Address.user_id == user_id)).all())


def add_address(session: Session, user: User, body) -> dict:
    coverage = assert_within_radius(session, body.latitude, body.longitude)
    if body.is_default:
        for a in session.exec(select(Address).where(Address.user_id == user.id)).all():
            a.is_default = False
            session.add(a)
    addr = Address(user_id=user.id, **body.model_dump())
    session.add(addr)
    session.commit()
    session.refresh(addr)
    return {"address": addr, "delivery": coverage}


def delete_address(session: Session, user_id: int, address_id: int) -> dict:
    addr = session.get(Address, address_id)
    if addr and addr.user_id == user_id:
        session.delete(addr)
        session.commit()
    return {"message": "deleted"}
