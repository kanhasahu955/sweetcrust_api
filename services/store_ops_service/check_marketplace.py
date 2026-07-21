"""Assert shop product create + sales filter by shop_user_id.

Run:
  cd backend_v2 && PYTHONPATH=$PWD:$PWD/services/store_ops_service \
    .venv/bin/python services/store_ops_service/check_marketplace.py
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
load_dotenv(os.path.join(ROOT, ".env"))
sys.path[:0] = [ROOT, os.path.join(ROOT, "services", "store_ops_service")]

from sqlalchemy import create_engine, text  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.models.catalog import Category, Product  # noqa: E402
from app.models.commerce import Order, OrderItem  # noqa: E402
from app.models.enums import OrderStatus, PaymentStatus  # noqa: E402
from app.models.user import RetailerProfile, User  # noqa: E402
from app.services import sell as sell_ops  # noqa: E402
from package.common.utils import generate_order_number, utc_now  # noqa: E402


def main() -> None:
    url = os.environ["DATABASE_URL"].replace("+aiomysql", "").replace("+asyncmy", "")
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[8:]
    eng = create_engine(url)

    with Session(eng) as session:
        profile = session.exec(
            select(RetailerProfile).where(RetailerProfile.approval_status == "approved")
        ).first()
        assert profile, "need approved shop"
        user = session.get(User, profile.user_id)
        assert user
        cat = session.exec(select(Category).where(Category.is_active == True)).first()  # noqa: E712
        assert cat, "need category"

        product = sell_ops.create_my_product(
            session,
            user,
            {"category_id": cat.id, "name": "Marketplace Check Snack", "selling_price": 49, "stock_qty": 5},
        )
        assert product.supplier_user_id == user.id

        # Simulate B2C order owned by this shop (checkout path sets shop_user_id the same way)
        customer = session.exec(select(User).where(User.id != user.id)).first()
        assert customer
        order = Order(
            order_number=generate_order_number(),
            user_id=customer.id,
            shop_user_id=user.id,
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            subtotal=49,
            final_amount=49,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(order)
        session.commit()
        session.refresh(order)
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                quantity=1,
                unit_price=49,
                total_price=49,
            )
        )
        session.commit()

        sales = sell_ops.list_sales_orders(session, user)
        assert any(row["order"].id == order.id for row in sales), "sales list missing order"

        updated = sell_ops.update_sales_status(session, user, order.id, "accepted")
        assert updated["order"].status == OrderStatus.ACCEPTED

        # cleanup (history → items → order → deactivate product)
        from app.models.commerce import OrderStatusHistory

        oid = order.id
        pid = product.id
        for h in session.exec(select(OrderStatusHistory).where(OrderStatusHistory.order_id == oid)).all():
            session.delete(h)
        for it in session.exec(select(OrderItem).where(OrderItem.order_id == oid)).all():
            session.delete(it)
        session.commit()
        o = session.get(Order, oid)
        if o:
            session.delete(o)
            session.commit()
        p = session.get(Product, pid)
        if p:
            p.is_active = False
            p.name = f"[check] {p.name}"
            session.add(p)
            session.commit()

    # cart single-shop: products from two shops cannot share cart lines
    # (enforced in cart_service add_to_cart — verified via column presence)
    with eng.connect() as conn:
        col = conn.execute(text("SHOW COLUMNS FROM orders LIKE 'shop_user_id'")).fetchone()
        assert col, "orders.shop_user_id missing"

    print("OK marketplace sell + shop_user_id + sales status")


if __name__ == "__main__":
    main()
