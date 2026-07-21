"""Cart, checkout, order lifecycle — port of monolith order_service."""
from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, col, select

from app.producers.events import emit_order_status
from app.models.catalog import Product
from app.models.commerce import (
    Cart,
    CartItem,
    Coupon,
    Invoice,
    Order,
    OrderItem,
    OrderStatusHistory,
    Payment,
    ReturnRequest,
)
from app.models.enums import OrderStatus, PaymentMethod, PaymentStatus, StockStatus, UserRole
from app.models.ops import BakerySettings, DeliveryPerson, DeliveryTracking
from app.models.user import Address, RetailerProfile, User
from app.services.geo import assert_within_radius
from app.services.notifications import notify
from package.common.errors import BadRequestError, ForbiddenError, NotFoundError
from package.common.utils import (
    generate_invoice_number,
    generate_order_number,
    generate_txn_id,
    stock_status_for,
    utc_now,
)
from package.logger import get_logger

logger = get_logger(__name__)


def _settings(session: Session) -> BakerySettings:
    s = session.exec(select(BakerySettings)).first()
    if not s:
        s = BakerySettings()
        session.add(s)
        session.commit()
        session.refresh(s)
    return s


def customer_unit_price(product: Product) -> float:
    if product.customer_price is not None:
        return float(product.customer_price)
    return float(product.selling_price or 0)


def get_or_create_cart(session: Session, user_id: int) -> Cart:
    cart = session.exec(select(Cart).where(Cart.user_id == user_id)).first()
    if not cart:
        cart = Cart(user_id=user_id)
        session.add(cart)
        session.commit()
        session.refresh(cart)
    return cart


def cart_summary(session: Session, user_id: int) -> dict:
    cart = get_or_create_cart(session, user_id)
    items = list(
        session.exec(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.saved_for_later == False)).all()  # noqa: E712
    )
    saved = list(
        session.exec(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.saved_for_later == True)).all()  # noqa: E712
    )
    settings = _settings(session)
    lines = []
    subtotal = 0.0
    shop_user_id: int | None = None
    for item in items:
        product = session.get(Product, item.product_id)
        line_total = item.unit_price * item.quantity
        subtotal += line_total
        sid = int(product.supplier_user_id) if product and product.supplier_user_id else None
        if shop_user_id is None and sid is not None:
            shop_user_id = sid
        lines.append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": product.name if product else "Product",
                "product_image": product.cover_image_url if product else None,
                "supplier_user_id": sid,
                "variant": item.variant,
                "flavor": item.flavor,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": line_total,
            }
        )
    discount = 0.0
    if cart.coupon_code:
        coupon = session.exec(
            select(Coupon).where(Coupon.code == cart.coupon_code, Coupon.is_active == True)  # noqa: E712
        ).first()
        if coupon:
            discount = _coupon_discount(coupon, subtotal)
    delivery = 0.0 if subtotal >= settings.free_delivery_min else settings.delivery_charge
    taxable = max(subtotal - discount, 0)
    gst = round(taxable * 0.05, 2)
    final = round(taxable + gst + delivery, 2)
    shop_name = None
    if shop_user_id:
        profile = session.exec(
            select(RetailerProfile).where(RetailerProfile.user_id == shop_user_id)
        ).first()
        shop_name = profile.shop_name if profile else None
    return {
        "cart_id": cart.id,
        "shop_user_id": shop_user_id,
        "shop_name": shop_name,
        "items": lines,
        "saved_for_later": [{"id": s.id, "product_id": s.product_id, "quantity": s.quantity} for s in saved],
        "coupon_code": cart.coupon_code,
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "gst": gst,
        "delivery_fee": delivery,
        "final_total": final,
    }


def add_to_cart(
    session: Session,
    user_id: int,
    product_id: int,
    quantity: int,
    variant: str | None,
    flavor: str | None,
    is_eggless: bool,
) -> dict:
    product = session.get(Product, product_id)
    if not product or not product.is_active:
        raise NotFoundError("Product not found")
    if not product.supplier_user_id:
        raise BadRequestError("Product is not sold by a shop")
    if product.stock_qty < quantity:
        raise BadRequestError("Insufficient stock")
    cart = get_or_create_cart(session, user_id)
    shop_id = int(product.supplier_user_id)
    # Single-shop cart: clear active lines from another shop, then add
    for item in session.exec(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.saved_for_later == False)  # noqa: E712
    ).all():
        other = session.get(Product, item.product_id)
        if other and other.supplier_user_id and int(other.supplier_user_id) != shop_id:
            session.delete(item)
    existing = session.exec(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
            CartItem.variant == variant,
            CartItem.saved_for_later == False,  # noqa: E712
        )
    ).first()
    if existing:
        existing.quantity += quantity
        session.add(existing)
    else:
        session.add(
            CartItem(
                cart_id=cart.id,
                product_id=product_id,
                quantity=quantity,
                variant=variant,
                flavor=flavor,
                is_eggless=is_eggless,
                unit_price=customer_unit_price(product),
            )
        )
    cart.updated_at = utc_now()
    session.add(cart)
    session.commit()
    return cart_summary(session, user_id)


def patch_cart_item(session: Session, user_id: int, item_id: int, quantity: int | None, saved_for_later: bool | None) -> dict:
    item = session.get(CartItem, item_id)
    if not item:
        return {"message": "not found"}
    cart = get_or_create_cart(session, user_id)
    if item.cart_id != cart.id:
        return {"message": "not found"}
    if quantity is not None:
        item.quantity = quantity
    if saved_for_later is not None:
        item.saved_for_later = saved_for_later
    session.add(item)
    session.commit()
    return cart_summary(session, user_id)


def remove_cart_item(session: Session, user_id: int, item_id: int) -> dict:
    item = session.get(CartItem, item_id)
    if item:
        cart = get_or_create_cart(session, user_id)
        if item.cart_id == cart.id:
            session.delete(item)
            session.commit()
    return cart_summary(session, user_id)


def apply_coupon(session: Session, user_id: int, code: str) -> dict:
    coupon = session.exec(
        select(Coupon).where(Coupon.code == code.upper(), Coupon.is_active == True)  # noqa: E712
    ).first()
    if not coupon:
        raise BadRequestError("Invalid coupon")
    cart = get_or_create_cart(session, user_id)
    cart.coupon_code = coupon.code
    session.add(cart)
    session.commit()
    return cart_summary(session, user_id)


def _coupon_discount(coupon: Coupon, subtotal: float) -> float:
    if subtotal < coupon.min_order_amount:
        return 0.0
    ctype = coupon.coupon_type.value if hasattr(coupon.coupon_type, "value") else str(coupon.coupon_type)
    if ctype in ("percentage", "first_order", "festival", "category", "product"):
        disc = subtotal * coupon.value / 100
        if coupon.max_discount:
            disc = min(disc, coupon.max_discount)
        return disc
    if ctype == "free_delivery":
        return 0.0
    return min(coupon.value, subtotal)


def checkout(session: Session, user_id: int, data) -> Order:
    summary = cart_summary(session, user_id)
    if not summary["items"]:
        raise BadRequestError("Cart is empty")
    settings = _settings(session)
    if summary["final_total"] < settings.min_order_value:
        raise BadRequestError(f"Minimum order value is ₹{settings.min_order_value}")
    address = session.get(Address, data.address_id)
    if not address or address.user_id != user_id:
        raise NotFoundError("Address not found")

    assert_within_radius(session, address.latitude, address.longitude)

    try:
        method = PaymentMethod(data.payment_method)
    except ValueError as exc:
        raise BadRequestError(f"Invalid payment method: {data.payment_method}") from exc
    if method == PaymentMethod.COD and not settings.cod_enabled:
        raise BadRequestError("Cash on delivery is disabled")

    shop_user_id = summary.get("shop_user_id")
    if not shop_user_id:
        raise BadRequestError("Cart items must belong to a shop")

    order = Order(
        order_number=generate_order_number(),
        user_id=user_id,
        shop_user_id=int(shop_user_id),
        address_id=address.id,
        status=OrderStatus.PLACED,
        payment_status=PaymentStatus.PENDING,
        payment_method=method,
        subtotal=summary["subtotal"],
        discount=summary["discount"],
        coupon_code=summary["coupon_code"],
        gst_amount=summary["gst"],
        delivery_fee=summary["delivery_fee"],
        final_amount=summary["final_total"],
        delivery_date=data.delivery_date,
        delivery_slot=data.delivery_slot,
        delivery_instructions=data.delivery_instructions,
        contactless=data.contactless,
        customer_phone=data.customer_phone,
        address_snapshot={
            "full_name": address.full_name,
            "phone": address.phone,
            "line1": address.line1,
            "line2": address.line2,
            "city": address.city,
            "state": address.state,
            "pincode": address.pincode,
            "latitude": address.latitude,
            "longitude": address.longitude,
        },
        estimated_delivery_at=utc_now() + timedelta(minutes=60),
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    for line in summary["items"]:
        product = session.get(Product, line["product_id"])
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=line["product_id"],
                product_name=line["product_name"],
                product_image=line["product_image"],
                variant=line["variant"],
                flavor=line["flavor"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                total_price=line["total_price"],
                unit_cost=float(product.purchase_cost or 0) if product else 0.0,
            )
        )
        if product:
            product.stock_qty = max(0, product.stock_qty - line["quantity"])
            product.stock_status = StockStatus(stock_status_for(product.stock_qty, product.low_stock_threshold))
            product.sales_count += line["quantity"]
            session.add(product)

    session.add(OrderStatusHistory(order_id=order.id, status=OrderStatus.PLACED, note="Order placed", created_by=user_id))
    session.add(
        Payment(
            order_id=order.id,
            user_id=user_id,
            amount=order.final_amount,
            method=method,
            status=PaymentStatus.PENDING,
            transaction_id=generate_txn_id(),
        )
    )

    cart = get_or_create_cart(session, user_id)
    for item in session.exec(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.saved_for_later == False)  # noqa: E712
    ).all():
        session.delete(item)
    cart.coupon_code = None
    session.add(cart)

    user = session.get(User, user_id)
    if user:
        user.total_orders += 1
        session.add(user)

    admin = session.exec(select(User).where(User.role == UserRole.ADMIN)).first()
    if admin:
        notify(session, admin.id, "order", "New order", f"Order {order.order_number} received", {"order_id": order.id})

    session.commit()
    session.refresh(order)
    emit_order_status(order.id, {"status": order.status.value, "user_id": order.user_id})
    logger.info("checkout order=%s user=%s", order.order_number, user_id)
    return order


def generate_invoice(session: Session, order: Order) -> Invoice:
    existing = session.exec(select(Invoice).where(Invoice.order_id == order.id)).first()
    if existing:
        return existing
    settings = _settings(session)
    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
    payment = session.exec(select(Payment).where(Payment.order_id == order.id).order_by(Payment.id.desc())).first()
    addr = order.address_snapshot or {}
    invoice = Invoice(
        order_id=order.id,
        invoice_number=generate_invoice_number(),
        bakery_name=settings.bakery_name,
        gstin=settings.gstin,
        customer_name=addr.get("full_name", "Customer"),
        customer_phone=order.customer_phone or addr.get("phone", ""),
        customer_address=", ".join(filter(None, [addr.get("line1"), addr.get("city"), addr.get("pincode")])),
        line_items={
            "items": [
                {"name": i.product_name, "qty": i.quantity, "unit_price": i.unit_price, "total": i.total_price}
                for i in items
            ]
        },
        subtotal=order.subtotal,
        discount=order.discount,
        gst_amount=order.gst_amount,
        delivery_fee=order.delivery_fee,
        grand_total=order.final_amount,
        payment_method=order.payment_method.value if order.payment_method else None,
        transaction_id=payment.transaction_id if payment else None,
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice


def update_order_status(
    session: Session,
    order_id: int,
    status: str,
    actor_id: int,
    note: str | None = None,
    delivery_person_id: int | None = None,
) -> Order:
    order = session.get(Order, order_id)
    if not order:
        raise NotFoundError("Order not found")
    try:
        new_status = OrderStatus(status)
    except ValueError as exc:
        raise BadRequestError(f"Invalid status: {status}") from exc
    order.status = new_status
    order.updated_at = utc_now()
    if new_status == OrderStatus.DELIVERED:
        order.delivered_at = utc_now()
        order.payment_status = PaymentStatus.PAID
        user = session.get(User, order.user_id)
        if user:
            user.total_spent += order.final_amount
            user.last_order_at = utc_now()
            session.add(user)
    if new_status == OrderStatus.CANCELLED:
        order.cancelled_at = utc_now()
        order.cancel_reason = note
    if delivery_person_id:
        person = session.get(DeliveryPerson, delivery_person_id)
        if not person:
            raise NotFoundError("Delivery person not found")
        order.delivery_person_id = delivery_person_id
        tracking = session.exec(select(DeliveryTracking).where(DeliveryTracking.order_id == order.id)).first()
        addr = order.address_snapshot or {}
        settings = _settings(session)
        if not tracking:
            session.add(
                DeliveryTracking(
                    order_id=order.id,
                    delivery_person_id=delivery_person_id,
                    bakery_lat=settings.latitude,
                    bakery_lng=settings.longitude,
                    customer_lat=addr.get("latitude"),
                    customer_lng=addr.get("longitude"),
                    rider_lat=settings.latitude,
                    rider_lng=settings.longitude,
                    eta_minutes=35,
                    distance_km=4.2,
                )
            )
        else:
            tracking.delivery_person_id = delivery_person_id
            session.add(tracking)
    session.add(OrderStatusHistory(order_id=order.id, status=new_status, note=note, created_by=actor_id))
    session.add(order)
    notify(
        session,
        order.user_id,
        "order",
        f"Order {new_status.value.replace('_', ' ').title()}",
        f"Your order {order.order_number} is now {new_status.value}",
        {"order_id": order.id, "status": new_status.value},
    )
    session.commit()
    session.refresh(order)
    emit_order_status(
        order_id,
        {
            "status": new_status.value,
            "user_id": order.user_id,
            "delivery_person_id": order.delivery_person_id,
        },
    )
    return order


def order_detail(session: Session, order_id: int, user_id: int | None = None, admin: bool = False) -> dict:
    order = session.get(Order, order_id)
    if not order:
        raise NotFoundError("Order not found")
    if not admin and order.user_id != user_id:
        raise ForbiddenError("Not your order")
    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
    timeline = list(
        session.exec(
            select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id).order_by(OrderStatusHistory.created_at)
        ).all()
    )
    payment = session.exec(select(Payment).where(Payment.order_id == order.id).order_by(Payment.id.desc())).first()
    invoice = session.exec(select(Invoice).where(Invoice.order_id == order.id)).first()
    tracking = session.exec(select(DeliveryTracking).where(DeliveryTracking.order_id == order.id)).first()
    delivery_person = session.get(DeliveryPerson, order.delivery_person_id) if order.delivery_person_id else None
    return {
        "order": order,
        "items": items,
        "timeline": timeline,
        "payment": payment,
        "invoice": invoice,
        "tracking": tracking,
        "delivery_person": delivery_person,
    }


def list_orders(session: Session, user_id: int | None = None, status_group: str | None = None) -> list[Order]:
    stmt = select(Order).order_by(Order.created_at.desc())
    if user_id:
        stmt = stmt.where(Order.user_id == user_id)
    if status_group == "active":
        stmt = stmt.where(col(Order.status).not_in([OrderStatus.DELIVERED, OrderStatus.CANCELLED]))
    elif status_group == "delivered":
        stmt = stmt.where(Order.status == OrderStatus.DELIVERED)
    elif status_group == "cancelled":
        stmt = stmt.where(Order.status == OrderStatus.CANCELLED)
    elif status_group:
        try:
            stmt = stmt.where(Order.status == OrderStatus(status_group))
        except ValueError:
            pass
    return list(session.exec(stmt.limit(100)).all())


def list_orders_or_returns(session: Session, user_id: int, tab: str) -> dict:
    if tab in ("returns", "refunds"):
        returns = list(session.exec(select(ReturnRequest).where(ReturnRequest.user_id == user_id)).all())
        return {"items": returns, "tab": tab}
    return {"items": list_orders(session, user_id, tab), "tab": tab}


def cancel_order(session: Session, order_id: int, user_id: int, reason: str = "Changed mind"):
    detail = order_detail(session, order_id, user_id)
    order = detail["order"]
    status = order.status.value if hasattr(order.status, "value") else str(order.status)
    if status in ("delivered", "cancelled", "out_for_delivery"):
        return {"message": "Cannot cancel at this stage"}
    return update_order_status(session, order_id, "cancelled", user_id, reason)


def rate_order(session: Session, order_id: int, user_id: int, rating: int, comment: str | None) -> dict:
    detail = order_detail(session, order_id, user_id)
    order = detail["order"]
    order.rating = rating
    order.rating_comment = comment
    session.add(order)
    session.commit()
    return {"message": "Thanks for rating!"}


def reorder(session: Session, order_id: int, user_id: int) -> dict:
    detail = order_detail(session, order_id, user_id)
    for item in detail["items"]:
        add_to_cart(session, user_id, item.product_id, item.quantity, item.variant, item.flavor, item.is_eggless)
    return cart_summary(session, user_id)


TRACK_STAGES = [
    "placed",
    "payment_received",
    "accepted",
    "preparing",
    "packed",
    "delivery_assigned",
    "picked_up",
    "out_for_delivery",
    "near_location",
    "delivered",
]


def track_order(session: Session, order_id: int, user_id: int) -> dict:
    detail = order_detail(session, order_id, user_id)
    return {
        "order": detail["order"],
        "tracking": detail["tracking"],
        "delivery_person": detail["delivery_person"],
        "timeline": detail["timeline"],
        "stages": TRACK_STAGES,
    }


def get_invoice(session: Session, order_id: int, user_id: int) -> Invoice:
    detail = order_detail(session, order_id, user_id)
    return detail["invoice"] or generate_invoice(session, detail["order"])
