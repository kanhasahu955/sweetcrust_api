from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.producers.events import emit_admin_event, emit_chat_message
from app.services.retailer_bff import _conversation_dict
from app.models.catalog import Product
from app.models.commerce import Coupon, CustomCakeRequest, Order, OrderItem, Payment, ReturnRequest
from app.models.enums import (
    CustomCakeStatus,
    NotificationType,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    StockStatus,
    UserRole,
)
from app.models.ledger import CreditLedgerEntry, SupplierPurchase
from app.models.ops import Banner, ChatMessage, Conversation, DeliveryPerson, Notification, SupportTicket
from app.models.user import RetailerProfile, User
from app.services import integrations as integ
from app.schemas.admin import BannerIn, CouponIn, MessageIn, ReturnAdminIn
from app.config import get_settings
from package.common.errors import NotFoundError
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def list_coupons(session: Session):
    return list(session.exec(select(Coupon).order_by(Coupon.created_at.desc())).all())


def create_coupon(session: Session, body: CouponIn) -> Coupon:
    c = Coupon(**body.model_dump())
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def list_banners(session: Session, *, shop_user_id: int | None = None):
    stmt = select(Banner).order_by(Banner.sort_order, Banner.id)
    if shop_user_id:
        stmt = stmt.where(Banner.shop_user_id == shop_user_id)
    return list(session.exec(stmt).all())


def create_banner(session: Session, body: BannerIn) -> Banner:
    b = Banner(**body.model_dump())
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


def list_tickets(session: Session):
    return list(session.exec(select(SupportTicket).order_by(SupportTicket.created_at.desc())).all())


def list_payments(session: Session):
    return list(session.exec(select(Payment).order_by(Payment.created_at.desc()).limit(200)).all())


def refund_payment(session: Session, payment_id: int, amount: float | None = None) -> Payment:
    p = session.get(Payment, payment_id)
    if not p:
        raise NotFoundError("Payment not found")
    refund_amt = amount or p.amount
    gateway_refund = None
    if (
        p.method == PaymentMethod.RAZORPAY
        and p.transaction_id
        and str(p.transaction_id).startswith("pay_")
        and get_settings().razorpay_configured
    ):
        gateway_refund = integ.refund_payment(p.transaction_id, refund_amt)
    p.refund_amount = refund_amt
    p.status = PaymentStatus.REFUNDED
    p.updated_at = utc_now()
    if gateway_refund:
        gw = dict(p.gateway_response or {})
        gw["refund"] = gateway_refund
        p.gateway_response = gw
    session.add(p)
    session.commit()
    session.refresh(p)
    logger.info("refund payment=%s amount=%s", payment_id, refund_amt)
    return p


def customer_presence(session: Session, customer_id: int) -> dict:
    user = session.get(User, customer_id)
    if not user:
        raise NotFoundError("Customer not found")
    return {
        "user_id": user.id,
        "is_online": user.is_online,
        "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
        "name": user.name,
        "phone": user.phone,
    }


def list_custom_cakes(session: Session):
    return list(session.exec(select(CustomCakeRequest).order_by(CustomCakeRequest.created_at.desc())).all())


def patch_custom_cake(session: Session, req_id: int, status: str, quoted_price: float | None) -> CustomCakeRequest:
    req = session.get(CustomCakeRequest, req_id)
    if not req:
        raise NotFoundError("Request not found")
    req.status = CustomCakeStatus(status)
    if quoted_price is not None:
        req.quoted_price = quoted_price
    req.updated_at = utc_now()
    session.add(req)
    session.add(
        Notification(
            user_id=req.user_id,
            type=NotificationType.CUSTOM_CAKE,
            title=f"Custom cake {req.status.value}",
            body=(
                f"Quoted price: ₹{req.quoted_price or req.estimated_price:.0f}"
                if req.quoted_price or req.estimated_price
                else "Updated"
            ),
            data={"id": req.id},
        )
    )
    session.commit()
    session.refresh(req)
    return req


def integrations_check() -> dict:
    return integ.credentials_check()


def reports(session: Session, period: str = "weekly") -> dict:
    days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
    since = utc_now() - timedelta(days=days)

    orders = list(session.exec(select(Order).where(Order.created_at >= since)).all())
    payments = list(session.exec(select(Payment).where(Payment.created_at >= since)).all())
    returns = list(session.exec(select(ReturnRequest).where(ReturnRequest.created_at >= since)).all())
    product_sales: dict[str, int] = {}
    order_ids = [o.id for o in orders if o.id is not None]
    items_by_order: dict[int, list] = {}
    if order_ids:
        for item in session.exec(select(OrderItem).where(OrderItem.order_id.in_(order_ids))).all():
            product_sales[item.product_name] = product_sales.get(item.product_name, 0) + item.quantity
            items_by_order.setdefault(item.order_id, []).append(item)

    paid_orders = [
        o
        for o in orders
        if o.payment_status == PaymentStatus.PAID
        or (o.order_type == "b2b_shop_order" and o.status == OrderStatus.DELIVERED)
    ]
    sales_total = round(sum(o.final_amount for o in paid_orders), 2)
    delivery_revenue = round(sum(float(o.delivery_fee or 0) for o in paid_orders), 2)

    cogs = 0.0
    item_margin = 0.0
    for o in paid_orders:
        for it in items_by_order.get(o.id or 0, []):
            cost = float(it.unit_cost or 0)
            if cost <= 0:
                p = session.get(Product, it.product_id)
                cost = float(p.purchase_cost or 0) if p else 0.0
            line_cogs = cost * int(it.quantity)
            line_rev = float(it.total_price or 0)
            cogs += line_cogs
            item_margin += line_rev - line_cogs
    cogs = round(cogs, 2)
    item_margin = round(item_margin, 2)

    riders = {r.id: r for r in session.exec(select(DeliveryPerson)).all()}
    rider_cost_total = 0.0
    by_rider: dict[int, dict] = {}
    for o in orders:
        if o.status != OrderStatus.DELIVERED or not o.delivery_person_id:
            continue
        rider = riders.get(o.delivery_person_id)
        trip = float(rider.default_trip_cost if rider else 40)
        rider_cost_total += trip
        bucket = by_rider.setdefault(
            o.delivery_person_id,
            {
                "rider_id": o.delivery_person_id,
                "name": rider.name if rider else "Rider",
                "trips": 0,
                "trip_cost": 0.0,
                "order_revenue": 0.0,
                "item_margin": 0.0,
            },
        )
        bucket["trips"] += 1
        bucket["trip_cost"] = round(bucket["trip_cost"] + trip, 2)
        bucket["order_revenue"] = round(bucket["order_revenue"] + float(o.final_amount or 0), 2)
        for it in items_by_order.get(o.id or 0, []):
            cost = float(it.unit_cost or 0)
            bucket["item_margin"] = round(bucket["item_margin"] + float(it.total_price or 0) - cost * it.quantity, 2)
    for b in by_rider.values():
        b["contribution"] = round(b["item_margin"] - b["trip_cost"], 2)
    rider_cost_total = round(rider_cost_total, 2)

    by_customer: dict[int, dict] = {}
    by_retailer: dict[int, dict] = {}
    for o in paid_orders:
        margin = 0.0
        for it in items_by_order.get(o.id or 0, []):
            cost = float(it.unit_cost or 0)
            if cost <= 0:
                p = session.get(Product, it.product_id)
                cost = float(p.purchase_cost or 0) if p else 0.0
            margin += float(it.total_price or 0) - cost * it.quantity
        is_b2b = str(o.order_type or "").startswith("b2b")
        target = by_retailer if is_b2b else by_customer
        u = session.get(User, o.user_id)
        name = (u.name if u else None) or (u.phone if u else str(o.user_id))
        if is_b2b:
            rp = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == o.user_id)).first()
            name = (rp.shop_name if rp else None) or name
        bucket = target.setdefault(
            o.user_id,
            {"user_id": o.user_id, "name": name, "orders": 0, "revenue": 0.0, "margin": 0.0},
        )
        bucket["orders"] += 1
        bucket["revenue"] = round(bucket["revenue"] + float(o.final_amount or 0), 2)
        bucket["margin"] = round(bucket["margin"] + margin, 2)

    collections = round(
        sum(
            float(e.amount)
            for e in session.exec(
                select(CreditLedgerEntry).where(
                    CreditLedgerEntry.created_at >= since,
                    CreditLedgerEntry.entry_type == "credit",
                )
            ).all()
        ),
        2,
    )
    purchases = list(session.exec(select(SupplierPurchase).where(SupplierPurchase.created_at >= since)).all())
    purchase_spend = round(sum(float(p.total) for p in purchases), 2)
    purchase_paid = round(sum(float(p.paid_amount or 0) for p in purchases), 2)
    payable_outstanding = round(
        sum(float(p.payable_balance or 0) for p in session.exec(select(RetailerProfile)).all()),
        2,
    )

    gross_profit = round(item_margin + delivery_revenue, 2)
    net_profit = round(gross_profit - rider_cost_total, 2)

    return {
        "period": period,
        "sales_total": sales_total,
        "revenue": sales_total,
        "order_count": len(orders),
        "payment_count": len(payments),
        "return_count": len(returns),
        "gst_total": round(sum(o.gst_amount for o in orders), 2),
        "cogs": cogs,
        "item_margin": item_margin,
        "delivery_revenue": delivery_revenue,
        "rider_cost": rider_cost_total,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "profit": net_profit,
        "collections": collections,
        "purchase_spend": purchase_spend,
        "purchase_paid": purchase_paid,
        "payable_outstanding": payable_outstanding,
        "product_sales": product_sales,
        "by_rider": sorted(by_rider.values(), key=lambda x: x["contribution"], reverse=True),
        "by_retailer": sorted(by_retailer.values(), key=lambda x: x["margin"], reverse=True),
        "by_customer": sorted(by_customer.values(), key=lambda x: x["margin"], reverse=True)[:40],
    }


def list_returns(session: Session):
    return list(session.exec(select(ReturnRequest).order_by(ReturnRequest.created_at.desc())).all())


def patch_return(session: Session, return_id: int, body: ReturnAdminIn) -> ReturnRequest:
    r = session.get(ReturnRequest, return_id)
    if not r:
        raise NotFoundError("Return not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(r, k, v)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def inventory(session: Session):
    low = list(session.exec(select(Product).where(Product.stock_status == StockStatus.LOW_STOCK)).all())
    out = list(session.exec(select(Product).where(Product.stock_status == StockStatus.OUT_OF_STOCK)).all())
    return {"low_stock": low, "out_of_stock": out}


def customers(session: Session):
    return list(session.exec(select(User).where(User.role == UserRole.CUSTOMER).order_by(User.created_at.desc())).all())


def list_chats(session: Session):
    rows = list(session.exec(select(Conversation).order_by(Conversation.updated_at.desc()).limit(100)).all())
    return [_conversation_dict(session, c) for c in rows]


def _admin_unread_total(session: Session) -> int:
    rows = session.exec(select(Conversation.unread_admin)).all()
    return int(sum(int(n or 0) for n in rows))


def chat_messages(session: Session, conversation_id: int):
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    # Mark-on-open: admin viewing a thread clears unread_admin (WhatsApp-style).
    dirty = False
    if (conv.unread_admin or 0) > 0:
        conv.unread_admin = 0
        session.add(conv)
        dirty = True
    inbound = list(
        session.exec(
            select(ChatMessage).where(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.sender_role != "admin",
                ChatMessage.is_read == False,  # noqa: E712
            )
        ).all()
    )
    for m in inbound:
        m.is_read = True
        m.is_delivered = True
        session.add(m)
        dirty = True
    if dirty:
        session.commit()
        emit_admin_event(
            "chat_unread",
            {
                "conversation_id": conversation_id,
                "unread_admin": 0,
                "total_unread": _admin_unread_total(session),
            },
        )
    return list(
        session.exec(
            select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at)
        ).all()
    )


def send_chat(session: Session, conversation_id: int, admin: User, body: MessageIn):
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    content = body.content or ""
    msg = ChatMessage(
        conversation_id=conversation_id,
        sender_id=admin.id,
        sender_role="admin",
        content=content,
    )
    conv.last_message = content[:500]
    conv.unread_customer = (conv.unread_customer or 0) + 1
    conv.ai_handed_over = True
    session.add(msg)
    session.add(conv)
    session.commit()
    session.refresh(msg)
    emit_chat_message(
        {
            "id": msg.id,
            "content": content,
            "sender_id": admin.id,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        },
        conversation_id=conversation_id,
        peer_user_id=conv.customer_id,
        sender_role="admin",
    )
    logger.info("admin message conversation=%s", conversation_id)
    return msg


def takeover(session: Session, conversation_id: int, admin: User):
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    conv.ai_handed_over = True
    conv.admin_id = admin.id
    session.add(conv)
    session.commit()
    return {"ok": True, "conversation_id": conversation_id}


def list_notifications(session: Session, user_id: int):
    return list(
        session.exec(
            select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(100)
        ).all()
    )


def mark_notifications_read(session: Session, user_id: int):
    rows = session.exec(select(Notification).where(Notification.user_id == user_id, Notification.is_read == False)).all()  # noqa: E712
    for n in rows:
        n.is_read = True
        session.add(n)
    session.commit()
    return {"ok": True, "count": len(rows)}
