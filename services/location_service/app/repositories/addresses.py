"""Address persistence."""
from __future__ import annotations
from sqlmodel import Session, select
from app.models.commerce import Address

def list_for_user(session: Session, user_id: int) -> list[Address]:
    return list(session.exec(select(Address).where(Address.user_id == user_id)).all())

def get(session: Session, address_id: int) -> Address | None:
    return session.get(Address, address_id)

def save(session: Session, addr: Address) -> Address:
    session.add(addr)
    session.commit()
    session.refresh(addr)
    return addr

def delete(session: Session, addr: Address) -> None:
    session.delete(addr)
    session.commit()
