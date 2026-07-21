"""Analytics HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import dashboard as dash_ops
from app.services import misc as misc_ops

def dashboard(session: Session):
    return dash_ops.dashboard(session)

def reports(session: Session, period: str = "weekly"):
    return misc_ops.reports(session, period)
