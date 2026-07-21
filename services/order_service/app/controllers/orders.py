"""Order HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import custom_cakes as cake_ops
from app.services import engagement as engage_ops
from app.services import orders as order_ops
from app.services import returns as return_ops

def list_orders(session: Session, user_id: int, tab: str = "active"):
    return order_ops.list_orders_or_returns(session, user_id, tab)

def detail(session: Session, order_id: int, user_id: int):
    return order_ops.order_detail(session, order_id, user_id)

def cancel(session: Session, order_id: int, user_id: int, reason: str):
    return order_ops.cancel_order(session, order_id, user_id, reason)

def reorder(session: Session, order_id: int, user_id: int):
    return order_ops.reorder(session, order_id, user_id)

def invoice(session: Session, order_id: int, user_id: int):
    return order_ops.get_invoice(session, order_id, user_id)

def rate(session: Session, order_id: int, user_id: int, rating: int, comment=None):
    return order_ops.rate_order(session, order_id, user_id, rating, comment)

def track(session: Session, order_id: int, user_id: int):
    return order_ops.track_order(session, order_id, user_id)

def share_track(session: Session, user, order_id: int):
    return engage_ops.create_share_link(session, user, order_id)

def create_cake(session: Session, user_id: int, body):
    return cake_ops.create_request(session, user_id, body)

def list_cakes(session: Session, user_id: int):
    return cake_ops.list_requests(session, user_id)

def create_return(session: Session, user_id: int, body):
    return return_ops.create_return(session, user_id, body)

def list_returns(session: Session, user_id: int):
    return return_ops.list_returns(session, user_id)

def return_detail(session: Session, return_id: int, user_id: int):
    return return_ops.return_detail(session, return_id, user_id)
