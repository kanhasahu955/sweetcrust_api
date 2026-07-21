from __future__ import annotations

from sqlmodel import Session, select

from app.models.catalog import Favorite, Product
from app.models.commerce import Payment, ReturnRequest
from app.models.user import Address, User


def profile_summary(session: Session, user: User) -> dict:
    favorites = []
    for f in session.exec(select(Favorite).where(Favorite.user_id == user.id)).all():
        if not f.product_id:
            continue
        product = session.get(Product, f.product_id)
        if product:
            favorites.append(product)

    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "phone": user.phone,
            "email": user.email,
            "language": user.language,
            "avatar_url": user.avatar_url,
        },
        "orders_count": user.total_orders,
        "total_spent": user.total_spent,
        "favorites": favorites,
        "addresses": list(session.exec(select(Address).where(Address.user_id == user.id)).all()),
        "payments": list(session.exec(select(Payment).where(Payment.user_id == user.id).limit(20)).all()),
        "returns": list(session.exec(select(ReturnRequest).where(ReturnRequest.user_id == user.id)).all()),
    }
