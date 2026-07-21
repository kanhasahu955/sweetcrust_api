"""Temporary retailer BFF ops (non-AI) until commerce owns B2B."""
from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.producers.events import emit_chat_message, emit_presence
from app.models.catalog import Category, Product
from app.models.commerce import Order, OrderItem, Payment
from app.models.enums import (
    CallStatus,
    CallType,
    ChatCategory,
    MessageType,
    NotificationType,
    OrderStatus,
    OrderType,
    PaymentMethod,
    PaymentStatus,
    UserRole,
)
from app.models.ops import BakerySettings, CallRecord, ChatMessage, Conversation, Notification
from app.models.user import RetailerProfile, User
from app.services import credit as credit_ops
from app.services import integrations as integ
from app.services import orders as order_ops
from app.services import products as product_ops
from app.schemas.admin import ProductIn, RetailerProfilePatchIn
from app.config import get_settings
from package.common.errors import BadRequestError, ForbiddenError, NotFoundError, ServiceUnavailableError
from package.common.utils import generate_order_number, generate_txn_id, slugify, utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def _shop_unit_price(product: Product) -> float:
    if product.shop_price is not None:
        return float(product.shop_price)
    if product.customer_price is not None:
        return float(product.customer_price)
    return float(product.selling_price or 0)


def me(session: Session, user: User) -> dict:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user.id)).first()
    if not profile:
        raise NotFoundError("Retailer profile not found")
    return {"user": user, "profile": profile}


def patch_me(session: Session, user: User, body: RetailerProfilePatchIn) -> dict:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user.id)).first()
    if not profile:
        raise NotFoundError("Retailer profile not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(profile, k, v)
    session.add(profile)
    session.commit()
    return me(session, user)


def submit(session: Session, user: User) -> dict:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user.id)).first()
    if not profile:
        raise NotFoundError("Retailer profile not found")
    profile.approval_status = "pending"
    session.add(profile)
    session.commit()
    logger.info("retailer %s submitted for approval", user.id)
    return {"approval_status": "pending", "message": "Submitted for bakery owner approval"}


def presence(session: Session, user: User, online: bool = True) -> dict:
    user.is_online = online
    user.last_seen_at = utc_now()
    session.add(user)
    session.commit()
    emit_presence(user.id, online)
    return {"is_online": user.is_online}


def catalog(session: Session):
    return list(session.exec(select(Product).where(Product.is_active == True, Product.is_draft == False)).all())  # noqa: E712


def my_orders(session: Session, user: User):
    return list(
        session.exec(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())).all()
    )


def get_order(session: Session, user: User, order_id: int) -> dict:
    order = session.get(Order, order_id)
    if not order or order.user_id != user.id:
        raise NotFoundError("Order not found")
    return order_ops.order_detail(session, order_id)


def request_product(session: Session, user: User, body: dict) -> dict:
    s = body.get("suggestions") or body
    name = (s.get("name") or s.get("title") or "").strip()
    if not name:
        raise BadRequestError("Product name is required")
    image_urls = [u for u in (body.get("image_urls") or []) if u]
    cover = body.get("cover_image") or (image_urls[0] if image_urls else None)
    if not cover:
        raise BadRequestError("Product photo is required")

    cat_name = (s.get("category") or "Village Supply").strip() or "Village Supply"
    cat = session.exec(select(Category).where(Category.name == cat_name)).first()
    if not cat:
        cat = Category(name=cat_name, slug=slugify(cat_name))
        session.add(cat)
        session.commit()
        session.refresh(cat)

    shop_price = float(s.get("shop_price") or s.get("selling_price") or s.get("recommended_selling_price") or 99)
    selling = float(s.get("selling_price") or s.get("customer_price") or shop_price)
    tags = list(s.get("tags") or [])
    tags.append(f"requested_by_shop:{user.id}")
    short = s.get("short_description")
    if isinstance(short, str):
        short = short[:500] or None
    product_in = ProductIn(
        category_id=cat.id,
        name=name[:200],
        short_description=short,
        description=s.get("description"),
        flavor=s.get("flavor"),
        weight=s.get("weight"),
        selling_price=selling,
        shop_price=shop_price,
        customer_price=float(s.get("customer_price") or selling),
        stock_qty=int(s.get("suggested_stock") or s.get("stock_qty") or 0),
        is_eggless=bool(s.get("is_eggless") or s.get("eggless")),
        tags=tags,
        cover_image_url=cover,
        is_draft=True,
        is_active=False,
    )
    product = product_ops.create_product(session, product_in, user.id)
    return {
        "id": product.id,
        "name": product.name,
        "is_draft": True,
        "message": "Sent to bakery owner for review. It will appear in catalog after they publish.",
        "shop_price": product.shop_price,
        "cover_image_url": product.cover_image_url,
    }


def create_bulk_order(
    session: Session,
    user: User,
    lines: list[dict],
    note: str | None = None,
    pay_mode: str = "credit",
) -> dict:
    if not lines:
        raise BadRequestError("Add at least one line item")
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user.id)).first()
    if not profile:
        raise BadRequestError("Shop profile required")
    status_val = getattr(profile, "approval_status", "approved") or "approved"
    if status_val == "incomplete":
        raise ForbiddenError("Complete your shop profile and submit for approval first")
    if status_val == "pending":
        raise ForbiddenError("Shop awaiting owner approval")
    if status_val != "approved":
        raise ForbiddenError("Shop not approved")
    if profile.is_blocked:
        raise ForbiddenError("Shop is blocked")

    subtotal = 0.0
    built: list[tuple[Product, int, float]] = []
    for line in lines:
        product_id = int(line["product_id"])
        qty = int(line.get("qty") or line.get("quantity") or 0)
        product = session.get(Product, product_id)
        if not product or not product.is_active:
            raise NotFoundError(f"Product {product_id} not found")
        min_qty = product.min_order_qty or 1
        if qty < min_qty:
            raise BadRequestError(f"{product.name}: min order qty is {min_qty}")
        unit = _shop_unit_price(product)
        subtotal += unit * qty
        built.append((product, qty, unit))

    gst = round(subtotal * 0.05, 2)
    final = round(subtotal + gst, 2)
    mode = (pay_mode or "credit").lower()
    if mode == "credit":
        if not profile.credit_allowed:
            raise BadRequestError("Credit not allowed for this shop")
        projected = round(profile.outstanding_balance + final, 2)
        if projected > profile.credit_limit:
            raise BadRequestError(
                f"Order ₹{final:.0f} would exceed credit limit "
                f"(outstanding ₹{profile.outstanding_balance:.0f} / limit ₹{profile.credit_limit:.0f})"
            )
        payment_method = PaymentMethod.CREDIT
        payment_status = PaymentStatus.PENDING
    elif mode == "upi":
        payment_method = PaymentMethod.UPI
        payment_status = PaymentStatus.PENDING
    elif mode == "razorpay":
        if not get_settings().razorpay_configured:
            raise ServiceUnavailableError("Razorpay not configured")
        payment_method = PaymentMethod.RAZORPAY
        payment_status = PaymentStatus.PENDING
    else:
        payment_method = PaymentMethod.COD
        payment_status = PaymentStatus.PENDING

    order = Order(
        order_number=generate_order_number(),
        user_id=user.id,
        order_type=OrderType.B2B_SHOP_ORDER.value,
        status=OrderStatus.PLACED,
        payment_status=payment_status,
        payment_method=payment_method,
        subtotal=subtotal,
        gst_amount=gst,
        delivery_fee=0.0,
        final_amount=final,
        delivery_date=date.today() + timedelta(days=1),
        delivery_slot="B2B village route",
        delivery_instructions=note or "Retailer bulk order",
        customer_phone=user.phone,
        address_snapshot={
            "channel": "retailer",
            "shop_name": profile.shop_name,
            "owner_name": profile.owner_name,
            "gstin": profile.gstin,
            "address_line": profile.address_line,
            "village": profile.village,
            "city": profile.city,
            "state": profile.state,
            "zone": profile.zone,
            "pay_mode": mode,
        },
        internal_notes="retailer_b2b",
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    for product, qty, unit in built:
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                product_image=product.cover_image_url,
                quantity=qty,
                unit_price=unit,
                total_price=round(unit * qty, 2),
                unit_cost=float(product.purchase_cost or 0),
                is_eggless=product.is_eggless,
            )
        )
    payment = Payment(
        order_id=order.id,
        user_id=user.id,
        amount=final,
        method=payment_method,
        status=payment_status,
        transaction_id=generate_txn_id(),
    )
    session.add(payment)
    session.commit()

    razorpay_checkout = None
    if mode == "razorpay":
        notes = {"order_id": str(order.id), "order_number": order.order_number, "user_id": str(user.id)}
        rz_order = integ.create_razorpay_order(amount_inr=final, receipt=order.order_number, notes=notes)
        link = integ.create_payment_link(
            amount_inr=final,
            description=f"SweetCrust {order.order_number}",
            reference_id=order.order_number,
            customer_phone=profile.contact_phone or user.phone,
            notes=notes,
        )
        payment.method = PaymentMethod.RAZORPAY
        payment.status = PaymentStatus.PROCESSING
        payment.gateway_response = {"razorpay_order": rz_order, "payment_link": link}
        session.add(payment)
        session.commit()
        razorpay_checkout = {**rz_order, "payment_link": link, "short_url": link.get("short_url")}

    if mode == "credit":
        credit_ops.debit_credit(
            session,
            user,
            final,
            order_id=order.id,
            note=f"Order {order.order_number}",
            created_by=user.id,
        )

    detail = order_ops.order_detail(session, order.id)
    if razorpay_checkout:
        detail["razorpay"] = razorpay_checkout
    return detail


def _first_admin(session: Session) -> User | None:
    return session.exec(select(User).where(User.role == UserRole.ADMIN)).first()


def _conversation_dict(session: Session, conv: Conversation) -> dict:
    peer = session.get(User, conv.customer_id)
    admin = session.get(User, conv.admin_id) if conv.admin_id else _first_admin(session)
    cat = conv.category.value if hasattr(conv.category, "value") else str(conv.category)
    is_retailer = cat.startswith("retailer")
    return {
        "id": conv.id,
        "category": cat,
        "customer_id": conv.customer_id,
        "participant_id": conv.customer_id,
        "participant_role": "retailer" if is_retailer else "customer",
        "participant_name": (peer.name if peer else None) or (peer.phone if peer else "User"),
        "participant_phone": peer.phone if peer else None,
        "participant_online": bool(getattr(peer, "is_online", False)) if peer else False,
        "participant_last_seen_at": peer.last_seen_at.isoformat() if peer and peer.last_seen_at else None,
        "admin_id": conv.admin_id or (admin.id if admin else None),
        "admin_online": bool(getattr(admin, "is_online", False)) if admin else False,
        "admin_name": (admin.name if admin else None) or "SweetCrust",
        "is_ai": conv.is_ai,
        "ai_handed_over": conv.ai_handed_over,
        "last_message": conv.last_message,
        "unread_customer": conv.unread_customer,
        "unread_admin": conv.unread_admin,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


def get_or_create_retailer_support(session: Session, retailer_id: int, *, ai: bool = False) -> Conversation:
    cat = ChatCategory.RETAILER_AI if ai else ChatCategory.RETAILER
    existing = session.exec(
        select(Conversation)
        .where(Conversation.customer_id == retailer_id, Conversation.category == cat)
        .order_by(Conversation.updated_at.desc())
    ).first()
    if existing and (not ai or existing.is_ai or not existing.ai_handed_over):
        return existing
    conv = Conversation(category=cat, customer_id=retailer_id, is_ai=ai)
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


def list_chats(session: Session, user: User) -> list[dict]:
    rows = list(
        session.exec(
            select(Conversation).where(Conversation.customer_id == user.id).order_by(Conversation.updated_at.desc())
        ).all()
    )
    return [_conversation_dict(session, c) for c in rows]


def open_support(session: Session, user: User, ai: bool = False) -> dict:
    conv = get_or_create_retailer_support(session, user.id, ai=ai)
    return _conversation_dict(session, conv)


def list_messages(session: Session, conversation_id: int, user: User) -> list[ChatMessage]:
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    if conv.customer_id != user.id:
        raise ForbiddenError("Forbidden")
    return list(
        session.exec(
            select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at)
        ).all()
    )


def send_message(
    session: Session,
    conversation_id: int,
    user: User,
    content: str | None,
    message_type: str = "text",
    media_url: str | None = None,
    metadata_json: dict | None = None,
) -> ChatMessage:
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    if conv.customer_id != user.id:
        raise ForbiddenError("Forbidden")
    try:
        msg_type = MessageType(str(message_type or "text").strip().lower())
    except ValueError:
        msg_type = MessageType.TEXT
    msg = ChatMessage(
        conversation_id=conversation_id,
        sender_id=user.id,
        sender_role="retailer",
        message_type=msg_type,
        content=content,
        media_url=media_url,
        metadata_json=metadata_json,
    )
    conv.last_message = (content or message_type)[:500]
    conv.updated_at = utc_now()
    conv.unread_admin = (conv.unread_admin or 0) + 1
    session.add(msg)
    session.add(conv)
    admin = _first_admin(session)
    if admin:
        session.add(
            Notification(
                user_id=admin.id,
                type=NotificationType.CHAT,
                title="New shop message",
                body=content or "New message",
                data={"conversation_id": conv.id},
            )
        )
    session.commit()
    session.refresh(msg)
    emit_chat_message(
        {
            "id": msg.id,
            "content": msg.content,
            "sender_id": user.id,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        },
        conversation_id=conversation_id,
        peer_user_id=admin.id if admin else None,
        sender_role="retailer",
    )
    return msg


def request_callback(session: Session, user: User, note: str | None = None) -> dict:
    admin = _first_admin(session)
    settings = session.exec(select(BakerySettings)).first()
    bakery_phone = (settings.phone if settings else None) or (admin.phone if admin else None)
    rec = CallRecord(
        caller_id=user.id,
        callee_id=admin.id if admin else None,
        call_type=CallType.PHONE,
        status=CallStatus.RINGING,
        direction="inbound",
        provider="phone",
        to_phone=bakery_phone,
        purpose=note or "Callback request from app",
        notes=f"retailer: {user.name or user.phone}",
        started_at=utc_now(),
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)
    if admin:
        session.add(
            Notification(
                user_id=admin.id,
                type=NotificationType.CALL,
                title="Callback requested",
                body=f"{user.name or user.phone} wants a call" + (f" — {note}" if note else ""),
                data={"call_id": rec.id, "from_user_id": user.id},
            )
        )
        session.commit()
    conv = get_or_create_retailer_support(session, user.id, ai=False)
    send_message(
        session,
        conv.id,
        user,
        f"📞 Callback requested{': ' + note if note else ''}. Bakery phone: {bakery_phone or '—'}",
    )
    return {
        "call_id": rec.id,
        "status": "requested",
        "bakery_phone": bakery_phone,
        "message": "Owner notified. You can also dial the bakery number shown.",
    }
