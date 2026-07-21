"""Rating HTTP adapters."""
from __future__ import annotations
from sqlmodel import Session
from app.services import orders as order_ops
from app.services import ratings as rating_ops

def rate_order(session: Session, order_id: int, user_id: int, rating: int, comment=None):
    return order_ops.rate_order(session, order_id, user_id, rating, comment)

def list_reviews(session: Session, product_id: int, limit: int = 20):
    return rating_ops.list_product_reviews(session, product_id, limit)

def add_review(session: Session, user_id: int, product_id: int, rating: int, comment=None, order_id=None):
    return rating_ops.add_product_review(session, user_id, product_id, rating, comment, order_id)
