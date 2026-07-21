"""Retailer shop seller mode: own catalog + B2C sales orders."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.catalog import Category, Product
from app.models.commerce import Order, OrderItem, OrderStatusHistory
from app.models.enums import OrderStatus, StockStatus
from app.models.user import RetailerProfile, User
from package.common.errors import BadRequestError, ForbiddenError, NotFoundError
from package.common.utils import slugify, stock_status_for, utc_now
from package.logger import get_logger

logger = get_logger(__name__)

_SHOP_STATUSES = {
    OrderStatus.PLACED,
    OrderStatus.ACCEPTED,
    OrderStatus.REJECTED,
    OrderStatus.PREPARING,
    OrderStatus.PACKED,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
    OrderStatus.CANCELLED,
}


def _approved_shop(session: Session, user: User) -> RetailerProfile:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user.id)).first()
    if not profile:
        raise NotFoundError("Shop profile not found")
    if profile.approval_status != "approved" or profile.is_blocked:
        raise ForbiddenError("Shop must be approved to sell")
    return profile


def list_categories(session: Session, user: User) -> list[Category]:
    _approved_shop(session, user)
    return list(session.exec(select(Category).where(Category.is_active == True).order_by(Category.display_order, Category.name)).all())  # noqa: E712


def list_my_products(session: Session, user: User) -> list[Product]:
    _approved_shop(session, user)
    return list(
        session.exec(select(Product).where(Product.supplier_user_id == user.id).order_by(Product.updated_at.desc())).all()
    )


def create_my_product(session: Session, user: User, data: dict) -> Product:
    profile = _approved_shop(session, user)
    name = (data.get("name") or "").strip()
    if not name:
        raise BadRequestError("name required")
    category_id = int(data.get("category_id") or 0)
    if not category_id or not session.get(Category, category_id):
        raise BadRequestError("Valid category_id required")
    selling = float(data.get("selling_price") or data.get("customer_price") or 0)
    if selling < 0:
        raise BadRequestError("selling_price must be >= 0")
    stock_qty = int(data.get("stock_qty") or 0)
    if stock_qty < 0:
        raise BadRequestError("stock_qty must be >= 0")

    base = slugify(name) or "product"
    slug = base
    i = 1
    while session.exec(select(Product).where(Product.slug == slug)).first():
        slug = f"{base}-{i}"
        i += 1

    p = Product(
        category_id=category_id,
        name=name,
        brand_name=profile.shop_name,
        supplier_user_id=user.id,
        slug=slug,
        short_description=data.get("short_description"),
        description=data.get("description"),
        selling_price=selling,
        customer_price=float(data["customer_price"]) if data.get("customer_price") is not None else selling,
        shop_price=float(data["shop_price"]) if data.get("shop_price") is not None else None,
        purchase_cost=float(data["purchase_cost"]) if data.get("purchase_cost") is not None else None,
        stock_qty=stock_qty,
        stock_status=StockStatus(stock_status_for(stock_qty)),
        cover_image_url=data.get("cover_image_url"),
        is_draft=False,
        is_active=bool(data.get("is_active", True)),
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    logger.info("shop %s created product %s", user.id, p.id)
    return p


def patch_my_product(session: Session, user: User, product_id: int, data: dict) -> Product:
    _approved_shop(session, user)
    p = session.get(Product, product_id)
    if not p or p.supplier_user_id != user.id:
        raise NotFoundError("Product not found")
    allowed = {
        "name",
        "category_id",
        "short_description",
        "description",
        "selling_price",
        "customer_price",
        "shop_price",
        "purchase_cost",
        "stock_qty",
        "cover_image_url",
        "is_active",
        "is_draft",
    }
    for k, v in data.items():
        if k in allowed and v is not None and hasattr(p, k):
            setattr(p, k, v)
    if "stock_qty" in data and data["stock_qty"] is not None:
        p.stock_status = StockStatus(stock_status_for(int(data["stock_qty"])))
    if "name" in data and data["name"]:
        p.name = str(data["name"]).strip()
    p.updated_at = utc_now()
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _order_dict(session: Session, order: Order) -> dict:
    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
    return {
        "order": order,
        "items": items,
    }


def list_sales_orders(session: Session, user: User) -> list[dict]:
    _approved_shop(session, user)
    rows = list(
        session.exec(
            select(Order)
            .where(Order.shop_user_id == user.id)
            .order_by(Order.created_at.desc())
            .limit(100)
        ).all()
    )
    return [_order_dict(session, o) for o in rows]


def update_sales_status(session: Session, user: User, order_id: int, status: str, note: str | None = None) -> dict:
    _approved_shop(session, user)
    order = session.get(Order, order_id)
    if not order or order.shop_user_id != user.id:
        raise NotFoundError("Order not found")
    try:
        new_status = OrderStatus(status)
    except ValueError as exc:
        raise BadRequestError(f"Invalid status: {status}") from exc
    if new_status not in _SHOP_STATUSES:
        raise BadRequestError(f"Shop cannot set status {status}")
    order.status = new_status
    order.updated_at = utc_now()
    if new_status == OrderStatus.DELIVERED:
        order.delivered_at = utc_now()
    if new_status == OrderStatus.CANCELLED:
        order.cancelled_at = utc_now()
        order.cancel_reason = note
    session.add(order)
    session.add(
        OrderStatusHistory(
            order_id=order.id,
            status=new_status,
            note=note or f"Shop updated to {new_status.value}",
            created_by=user.id,
        )
    )
    session.commit()
    session.refresh(order)
    return _order_dict(session, order)
