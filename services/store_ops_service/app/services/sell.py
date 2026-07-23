"""Retailer shop seller mode: own catalog + B2C sales + banners/coupons."""
from __future__ import annotations

import json
from datetime import timedelta

from sqlmodel import Session, col, select

from app.config import get_settings
from app.models.catalog import Category, Product
from app.models.commerce import Coupon, Order, OrderItem, OrderStatusHistory
from app.models.enums import NotificationType, OrderStatus, StockStatus
from app.models.ops import BakerySettings, Banner, Notification
from app.models.user import RetailerProfile, User
from app.producers.events import emit_order_status, emit_user_event
from app.services import integrations as integ
from app.services.units import normalize_unit
from package.common.errors import BadRequestError, ForbiddenError, NotFoundError, ServiceUnavailableError
from package.common.utils import slugify, stock_status_for, utc_now
from package.logger import get_logger

logger = get_logger(__name__)

# Defaults if BakerySettings.tax_settings has no sell_* prices
_DEFAULT_MONTHLY = 499.0
_DEFAULT_YEARLY = 4990.0

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


def _shop(session: Session, user: User) -> RetailerProfile:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user.id)).first()
    if not profile:
        raise NotFoundError("Shop profile not found")
    if profile.is_blocked:
        raise ForbiddenError("Shop is blocked")
    return profile


def _approved_shop(session: Session, user: User) -> RetailerProfile:
    profile = _shop(session, user)
    if profile.approval_status != "approved":
        raise ForbiddenError("Shop must be KYC-approved first")
    return profile


def _selling_shop(session: Session, user: User) -> RetailerProfile:
    """KYC approved + sell subscription approved and not expired."""
    profile = _approved_shop(session, user)
    status = getattr(profile, "sell_subscription_status", None) or "none"
    exp = getattr(profile, "sell_subscription_expires_at", None)
    if status == "approved" and exp and exp < utc_now():
        profile.sell_subscription_status = "expired"
        session.add(profile)
        session.commit()
        status = "expired"
    if status != "approved":
        raise ForbiddenError("Active sell subscription required — choose a plan and pay via Razorpay")
    return profile


def _plan_prices(session: Session) -> dict[str, float]:
    row = session.exec(select(BakerySettings)).first()
    tax = (row.tax_settings if row and isinstance(row.tax_settings, dict) else {}) or {}
    monthly = float(tax.get("sell_monthly_price") or _DEFAULT_MONTHLY)
    yearly = float(tax.get("sell_yearly_price") or _DEFAULT_YEARLY)
    return {"monthly": monthly, "yearly": yearly}


def list_sell_plans(session: Session, user: User) -> list[dict]:
    _approved_shop(session, user)
    prices = _plan_prices(session)
    return [
        {
            "cadence": "monthly",
            "label": "Monthly",
            "price": prices["monthly"],
            "days": 30,
            "blurb": "List products, banners & offers for 30 days",
        },
        {
            "cadence": "yearly",
            "label": "Yearly",
            "price": prices["yearly"],
            "days": 365,
            "blurb": "Best value — full year of selling tools",
            "save_hint": "Save vs monthly",
        },
    ]


def subscription_status(session: Session, user: User) -> dict:
    profile = _shop(session, user)
    status = getattr(profile, "sell_subscription_status", None) or "none"
    exp = getattr(profile, "sell_subscription_expires_at", None)
    if status == "approved" and exp and exp < utc_now():
        profile.sell_subscription_status = "expired"
        session.add(profile)
        session.commit()
        status = "expired"
        exp = profile.sell_subscription_expires_at
    prices = _plan_prices(session)
    return {
        "approval_status": profile.approval_status,
        "sell_subscription_status": status,
        "sell_plan": getattr(profile, "sell_plan", None),
        "sell_subscription_expires_at": exp.isoformat() if exp else None,
        "can_sell": profile.approval_status == "approved" and status == "approved" and not profile.is_blocked,
        "plans": [
            {"cadence": "monthly", "label": "Monthly", "price": prices["monthly"], "days": 30},
            {"cadence": "yearly", "label": "Yearly", "price": prices["yearly"], "days": 365},
        ],
        "razorpay_configured": bool(get_settings().razorpay_configured),
    }


def request_sell_subscription(session: Session, user: User) -> dict:
    """Legacy no-pay request — kept for admin comps; prefer Razorpay pay endpoints."""
    profile = _approved_shop(session, user)
    status = getattr(profile, "sell_subscription_status", None) or "none"
    if status == "approved":
        return {"sell_subscription_status": "approved", "message": "Already approved to sell"}
    profile.sell_subscription_status = "pending"
    session.add(profile)
    session.commit()
    return {"sell_subscription_status": "pending", "message": "Submitted for admin approval"}


def _activate_paid(session: Session, profile: RetailerProfile, cadence: str, amount: float, payment_ref: str) -> RetailerProfile:
    days = 365 if cadence == "yearly" else 30
    now = utc_now()
    base = profile.sell_subscription_expires_at if (
        profile.sell_subscription_status == "approved"
        and profile.sell_subscription_expires_at
        and profile.sell_subscription_expires_at > now
    ) else now
    profile.sell_subscription_status = "approved"
    profile.sell_plan = cadence
    profile.sell_subscription_expires_at = base + timedelta(days=days)
    profile.sell_rz_pending = None
    session.add(profile)
    # Billing history row (no order_id) — retailer Payments tab reads these
    session.add(
        Notification(
            user_id=profile.user_id,
            type=NotificationType.PAYMENT,
            title=f"Sell plan · {cadence}",
            body=f"Paid ₹{amount:.0f} via Razorpay · active until {profile.sell_subscription_expires_at.date().isoformat()}",
            data={
                "kind": "sell_subscription",
                "purpose": "subscription",
                "cadence": cadence,
                "amount": amount,
                "payment_ref": payment_ref,
                "expires_at": profile.sell_subscription_expires_at.isoformat(),
                "paid_at": now.isoformat(),
            },
        )
    )
    session.commit()
    session.refresh(profile)
    try:
        from app.services import invoices as invoice_ops

        user = session.get(User, profile.user_id)
        if user:
            invoice_ops.issue_subscription(
                session,
                user=user,
                profile=profile,
                cadence=cadence,
                amount=amount,
                payment_ref=payment_ref,
                expires_at_iso=profile.sell_subscription_expires_at.isoformat(),
            )
    except Exception:
        logger.exception("subscription invoice failed for shop %s", profile.user_id)
    logger.info(
        "shop %s sell plan %s activated via %s amount=%.2f expires=%s",
        profile.user_id,
        cadence,
        payment_ref,
        amount,
        profile.sell_subscription_expires_at,
    )
    return profile


def create_sell_subscription_payment(session: Session, user: User, cadence: str) -> dict:
    profile = _approved_shop(session, user)
    cadence = (cadence or "").strip().lower()
    if cadence not in {"monthly", "yearly"}:
        raise BadRequestError("cadence must be monthly or yearly")
    if not get_settings().razorpay_configured:
        raise ServiceUnavailableError("Razorpay not configured — ask admin to enable payments")

    prices = _plan_prices(session)
    amount = prices[cadence]
    notes = {
        "kind": "sell_subscription",
        "user_id": str(user.id),
        "cadence": cadence,
        "amount": f"{amount:.2f}",
        "shop_name": profile.shop_name or "",
    }
    receipt = f"sell-{user.id}-{cadence}-{int(utc_now().timestamp())}"[:40]
    link = integ.create_payment_link(
        amount_inr=amount,
        description=f"SweetCrust sell plan · {cadence} · {profile.shop_name}",
        reference_id=receipt,
        customer_phone=profile.contact_phone or user.phone,
        notes=notes,
    )
    link_id = str(link.get("payment_link_id") or "")
    if not link_id:
        raise BadRequestError("Could not create Razorpay payment link")
    profile.sell_rz_pending = f"{link_id}:{cadence}:{amount:.2f}"
    if (profile.sell_subscription_status or "none") != "approved":
        profile.sell_subscription_status = "pending"
    session.add(profile)
    session.commit()
    return {
        "cadence": cadence,
        "amount": amount,
        "currency": "INR",
        "payment_link_id": link_id,
        "short_url": link.get("short_url"),
        "payment_link": link,
        "sell_subscription_status": profile.sell_subscription_status,
        "message": "Pay with Razorpay to activate your sell plan",
    }


def confirm_sell_subscription_payment(session: Session, user: User) -> dict:
    """After Razorpay payment-link return — poll link status and activate if paid."""
    profile = _approved_shop(session, user)
    pending = (getattr(profile, "sell_rz_pending", None) or "").strip()
    if not pending:
        if (profile.sell_subscription_status or "") == "approved":
            out = subscription_status(session, user)
            out["message"] = "Already active"
            return out
        raise BadRequestError("No pending sell payment — start checkout again")

    try:
        link_id, cadence, amount_s = pending.split(":", 2)
        amount = float(amount_s)
    except ValueError as exc:
        raise BadRequestError("Invalid pending payment state") from exc

    data = integ.get_payment_link(link_id)
    status = str(data.get("status") or "").lower()
    if status != "paid":
        return {
            **subscription_status(session, user),
            "payment_status": status or "created",
            "message": "Payment not completed yet — finish Razorpay checkout, then tap Confirm payment",
        }

    _activate_paid(session, profile, cadence, amount, link_id)
    out = subscription_status(session, user)
    out["message"] = "Sell subscription activated"
    out["payment_status"] = "paid"
    return out


def list_categories(session: Session, user: User) -> list[dict]:
    """Platform categories + this shop's own top-level categories (+ legacy subs)."""
    _approved_shop(session, user)
    platform = list(
        session.exec(
            select(Category)
            .where(
                Category.is_active == True,  # noqa: E712
                col(Category.parent_id).is_(None),
                col(Category.owner_user_id).is_(None),
            )
            .order_by(Category.display_order, Category.name)
        ).all()
    )
    mine = list(
        session.exec(
            select(Category)
            .where(
                Category.is_active == True,  # noqa: E712
                Category.owner_user_id == user.id,
                col(Category.parent_id).is_(None),
            )
            .order_by(Category.display_order, Category.name)
        ).all()
    )
    # Legacy shop subcats still selectable for older products
    legacy_subs = list(
        session.exec(
            select(Category)
            .where(
                Category.is_active == True,  # noqa: E712
                Category.owner_user_id == user.id,
                col(Category.parent_id).is_not(None),
            )
            .order_by(Category.display_order, Category.name)
        ).all()
    )
    out: list[dict] = []
    for c in mine:
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "slug": c.slug,
                "parent_id": None,
                "owner_user_id": c.owner_user_id,
                "kind": "shop",
            }
        )
    for c in platform:
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "slug": c.slug,
                "parent_id": None,
                "owner_user_id": None,
                "kind": "admin",
            }
        )
    for s in legacy_subs:
        out.append(
            {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "parent_id": s.parent_id,
                "owner_user_id": s.owner_user_id,
                "kind": "sub",
            }
        )
    return out


def create_category(session: Session, user: User, data: dict) -> Category:
    """Shop creates a top-level category (visible to admin via owner_user_id)."""
    profile = _selling_shop(session, user)
    name = (data.get("name") or "").strip()
    if not name:
        raise BadRequestError("Category name is required")
    if len(name) < 2:
        raise BadRequestError("Name must be at least 2 characters")
    if len(name) > 120:
        raise BadRequestError("Name is too long")

    dup = session.exec(
        select(Category).where(
            Category.owner_user_id == user.id,
            col(Category.parent_id).is_(None),
            Category.name == name,
            Category.is_active == True,  # noqa: E712
        )
    ).first()
    if dup:
        raise BadRequestError("You already have this category")

    # Block names that collide with platform (admin) top-level categories
    platform = list(
        session.exec(
            select(Category).where(
                Category.is_active == True,  # noqa: E712
                col(Category.parent_id).is_(None),
                col(Category.owner_user_id).is_(None),
            )
        ).all()
    )
    clash = next((c for c in platform if (c.name or "").strip().lower() == name.lower()), None)
    if clash:
        raise BadRequestError(
            f"“{clash.name}” is already a platform category. Choose a different name."
        )

    base = slugify(f"{profile.shop_name}-{name}") or "cat"
    slug = base
    i = 1
    while session.exec(select(Category).where(Category.slug == slug)).first():
        slug = f"{base}-{i}"
        i += 1

    cat = Category(
        name=name,
        slug=slug,
        description=data.get("description"),
        image_url=data.get("image_url"),
        parent_id=None,
        owner_user_id=user.id,
        is_active=True,
    )
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


# Back-compat alias for older imports
create_subcategory = create_category


def list_my_products(session: Session, user: User) -> list[Product]:
    _selling_shop(session, user)
    return list(
        session.exec(
            select(Product)
            .where(
                Product.supplier_user_id == user.id,
                Product.is_active == True,  # noqa: E712 — soft-deleted products hidden
            )
            .order_by(Product.updated_at.desc())
        ).all()
    )


def create_my_product(session: Session, user: User, data: dict) -> Product:
    profile = _selling_shop(session, user)
    name = (data.get("name") or "").strip()
    if not name:
        raise BadRequestError("Product name is required")
    if len(name) < 2:
        raise BadRequestError("Product name must be at least 2 characters")
    if len(name) > 160:
        raise BadRequestError("Product name is too long")
    category_id = int(data.get("category_id") or 0)
    if category_id <= 0:
        raise BadRequestError("Category is required")
    cat = session.get(Category, category_id)
    if not cat:
        raise BadRequestError("Valid category is required")
    # Must be own subcategory or (legacy) any active category the shop can use
    if cat.owner_user_id and cat.owner_user_id != user.id:
        raise ForbiddenError("Category not yours")
    if cat.owner_user_id is None and cat.parent_id is None:
        # Allow placing on admin parent for convenience, but prefer subcats
        pass

    selling = float(data.get("selling_price") or data.get("customer_price") or 0)
    if selling <= 0:
        raise BadRequestError("Price must be greater than 0")
    stock_qty = int(data.get("stock_qty") or 0)
    if stock_qty < 0:
        raise BadRequestError("Stock must be 0 or more")
    short = (data.get("short_description") or "")
    if isinstance(short, str) and len(short) > 300:
        raise BadRequestError("Short description is too long")
    details = (data.get("description") or "")
    if isinstance(details, str) and len(details) > 4000:
        raise BadRequestError("Details are too long")

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
        weight=data.get("weight"),
        unit_label=normalize_unit(data.get("unit_label")),
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
    _selling_shop(session, user)
    p = session.get(Product, product_id)
    if not p or p.supplier_user_id != user.id:
        raise NotFoundError("Product not found")
    allowed = {
        "name",
        "category_id",
        "short_description",
        "description",
        "weight",
        "unit_label",
        "selling_price",
        "customer_price",
        "shop_price",
        "purchase_cost",
        "stock_qty",
        "cover_image_url",
        "is_active",
        "is_draft",
    }
    if "name" in data and data["name"] is not None:
        name = str(data["name"]).strip()
        if not name:
            raise BadRequestError("Product name is required")
        if len(name) < 2:
            raise BadRequestError("Product name must be at least 2 characters")
        data = {**data, "name": name}
    if "category_id" in data and data["category_id"] is not None:
        cid = int(data["category_id"] or 0)
        if cid <= 0:
            raise BadRequestError("Category is required")
        cat = session.get(Category, cid)
        if not cat:
            raise BadRequestError("Valid category is required")
        if cat.owner_user_id and cat.owner_user_id != user.id:
            raise ForbiddenError("Category not yours")
    if "selling_price" in data and data["selling_price"] is not None:
        if float(data["selling_price"]) <= 0:
            raise BadRequestError("Price must be greater than 0")
    if "stock_qty" in data and data["stock_qty"] is not None:
        if int(data["stock_qty"]) < 0:
            raise BadRequestError("Stock must be 0 or more")
    if "unit_label" in data and data["unit_label"] is not None:
        data = {**data, "unit_label": normalize_unit(data.get("unit_label"))}
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


def delete_my_product(session: Session, user: User, product_id: int) -> dict:
    _selling_shop(session, user)
    p = session.get(Product, product_id)
    if not p or p.supplier_user_id != user.id:
        raise NotFoundError("Product not found")
    # Soft-delete so order history / FKs stay intact
    p.is_active = False
    p.is_draft = True
    p.updated_at = utc_now()
    session.add(p)
    session.commit()
    logger.info("shop %s deleted product %s", user.id, product_id)
    return {"ok": True, "id": product_id, "deleted": True}


def list_banners(session: Session, user: User) -> list[Banner]:
    _selling_shop(session, user)
    return list(
        session.exec(
            select(Banner).where(Banner.shop_user_id == user.id).order_by(Banner.sort_order, col(Banner.id).desc())
        ).all()
    )


def create_banner(session: Session, user: User, data: dict) -> Banner:
    _selling_shop(session, user)
    title = (data.get("title") or "").strip()
    image_url = (data.get("image_url") or "").strip()
    theme = (data.get("theme_color") or "").strip()
    if not title:
        raise BadRequestError("Banner title is required")
    # Theme-only banners store as theme:#hex or theme:#hex,#hex2 (no migration)
    if not image_url and theme:
        if not theme.startswith("#") and not theme.startswith("theme:"):
            theme = f"#{theme.lstrip('#')}"
        image_url = theme if theme.startswith("theme:") else f"theme:{theme}"
    if not image_url:
        raise BadRequestError("Upload an image or pick a theme color")

    link_type = (data.get("link_type") or "").strip().lower() or None
    link_value = (data.get("link_value") or "").strip() or None
    allowed = {None, "shop", "order", "coupon", "url", "none"}
    if link_type not in allowed:
        raise BadRequestError("Invalid banner action")
    if link_type == "none":
        link_type, link_value = None, None
    if link_type == "coupon" and not link_value:
        raise BadRequestError("Pick a coupon / offer code for this banner")
    if link_type == "url" and not link_value:
        raise BadRequestError("Enter a link URL for this banner")

    b = Banner(
        title=title,
        subtitle=data.get("subtitle"),
        image_url=image_url,
        link_type=link_type,
        link_value=link_value,
        is_active=bool(data.get("is_active", True)),
        sort_order=int(data.get("sort_order") or 0),
        shop_user_id=user.id,
    )
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


def patch_banner(session: Session, user: User, banner_id: int, data: dict) -> Banner:
    _selling_shop(session, user)
    b = session.get(Banner, banner_id)
    if not b or b.shop_user_id != user.id:
        raise NotFoundError("Banner not found")
    for k in ("title", "subtitle", "image_url", "link_type", "link_value", "is_active", "sort_order"):
        if k in data and data[k] is not None:
            setattr(b, k, data[k])
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


def list_coupons(session: Session, user: User) -> list[Coupon]:
    _selling_shop(session, user)
    return list(
        session.exec(select(Coupon).where(Coupon.shop_user_id == user.id).order_by(Coupon.created_at.desc())).all()
    )


def _pack_coupon_description(data: dict) -> str | None:
    """Stash theme/action in description JSON so offers match banner UX without a migration."""
    text = (data.get("description") or "").strip()
    theme = (data.get("theme_color") or "").strip()
    action = (data.get("link_action") or data.get("link_type") or "").strip().lower()
    if action in ("", "none", "apply"):
        action = "apply" if action != "none" else "none"
    if action not in ("apply", "shop", "order", "none"):
        action = "apply"
    if not theme and not text and action == "apply":
        return None
    return json.dumps({"t": theme or None, "a": action, "d": text or ""}, separators=(",", ":"))


def create_coupon(session: Session, user: User, data: dict) -> Coupon:
    _selling_shop(session, user)
    code = (data.get("code") or "").strip().upper()
    title = (data.get("title") or "").strip()
    if not code or not title:
        raise BadRequestError("code and title required")
    if len(code) < 3:
        raise BadRequestError("Code must be at least 3 characters")
    if session.exec(select(Coupon).where(Coupon.code == code)).first():
        raise BadRequestError("Coupon code already exists")
    coupon_type = (data.get("coupon_type") or "percentage").strip().lower()
    if coupon_type not in ("percentage", "flat"):
        raise BadRequestError("coupon_type must be percentage or flat")
    value = float(data.get("value") or 0)
    if value <= 0:
        raise BadRequestError("Offer value must be greater than 0")
    if coupon_type == "percentage" and value > 100:
        raise BadRequestError("Percentage cannot exceed 100")
    c = Coupon(
        code=code,
        title=title,
        description=_pack_coupon_description(data),
        coupon_type=coupon_type,
        value=value,
        min_order_amount=float(data.get("min_order_amount") or 0),
        max_discount=float(data["max_discount"]) if data.get("max_discount") is not None else None,
        usage_limit=int(data["usage_limit"]) if data.get("usage_limit") is not None else None,
        is_active=bool(data.get("is_active", True)),
        shop_user_id=user.id,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def patch_coupon(session: Session, user: User, coupon_id: int, data: dict) -> Coupon:
    _selling_shop(session, user)
    c = session.get(Coupon, coupon_id)
    if not c or c.shop_user_id != user.id:
        raise NotFoundError("Coupon not found")
    for k in (
        "title",
        "description",
        "coupon_type",
        "value",
        "min_order_amount",
        "max_discount",
        "usage_limit",
        "is_active",
    ):
        if k in data and data[k] is not None:
            setattr(c, k, data[k])
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _enum_val(v) -> str | None:
    if v is None:
        return None
    return v.value if hasattr(v, "value") else str(v)


def _order_dict(session: Session, order: Order) -> dict:
    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
    addr = order.address_snapshot or {}
    status = _enum_val(order.status) or "placed"
    steps = ["placed", "accepted", "preparing", "packed", "out_for_delivery", "delivered"]
    step_idx = steps.index(status) if status in steps else -1
    return {
        "id": order.id,
        "order_id": order.id,
        "order_number": order.order_number,
        "status": status,
        "payment_status": _enum_val(order.payment_status),
        "payment_method": _enum_val(order.payment_method),
        "subtotal": float(order.subtotal or 0),
        "gst_amount": float(order.gst_amount or 0),
        "delivery_fee": float(order.delivery_fee or 0),
        "discount": float(order.discount or 0),
        "final_amount": float(order.final_amount or 0),
        "paid_amount": float(getattr(order, "paid_amount", 0) or 0),
        "customer_phone": order.customer_phone or addr.get("phone"),
        "customer_name": addr.get("full_name") or addr.get("name") or "Customer",
        "address": addr,
        "delivery_slot": order.delivery_slot,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "step_index": step_idx,
        "steps": steps,
        "lines": [
            {
                "product_id": i.product_id,
                "product_name": i.product_name,
                "product_image": i.product_image,
                "qty": i.quantity,
                "unit_price": float(i.unit_price or 0),
                "line_total": float(i.total_price or 0),
                "variant": i.variant,
            }
            for i in items
        ],
        # keep nested shape for older clients
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "status": status,
            "final_amount": float(order.final_amount or 0),
            "created_at": order.created_at.isoformat() if order.created_at else None,
        },
        "items": [
            {
                "product_name": i.product_name,
                "quantity": i.quantity,
                "unit_price": float(i.unit_price or 0),
                "total_price": float(i.total_price or 0),
            }
            for i in items
        ],
    }


def list_sales_orders(session: Session, user: User) -> list[dict]:
    _selling_shop(session, user)
    rows = list(
        session.exec(
            select(Order).where(Order.shop_user_id == user.id).order_by(Order.created_at.desc()).limit(100)
        ).all()
    )
    return [_order_dict(session, o) for o in rows]


def admin_shop_catalog(session: Session, retailer_user_id: int) -> dict:
    """Admin view of a shop's sell catalog: products, banners, offers, B2C sales."""
    profile = session.exec(
        select(RetailerProfile).where(RetailerProfile.user_id == retailer_user_id)
    ).first()
    if not profile:
        raise NotFoundError("Shop not found")

    products = list(
        session.exec(
            select(Product)
            .where(Product.supplier_user_id == retailer_user_id)
            .order_by(Product.updated_at.desc())
        ).all()
    )
    banners = list(
        session.exec(
            select(Banner)
            .where(Banner.shop_user_id == retailer_user_id)
            .order_by(Banner.sort_order, col(Banner.id).desc())
        ).all()
    )
    coupons = list(
        session.exec(
            select(Coupon)
            .where(Coupon.shop_user_id == retailer_user_id)
            .order_by(Coupon.created_at.desc())
        ).all()
    )
    sales_rows = list(
        session.exec(
            select(Order)
            .where(Order.shop_user_id == retailer_user_id)
            .order_by(Order.created_at.desc())
            .limit(50)
        ).all()
    )
    active_products = sum(1 for p in products if p.is_active)
    return {
        "shop_user_id": retailer_user_id,
        "shop_name": profile.shop_name,
        "products": products,
        "banners": banners,
        "coupons": coupons,
        "sales": [_order_dict(session, o) for o in sales_rows],
        "counts": {
            "products": len(products),
            "products_active": active_products,
            "banners": len(banners),
            "coupons": len(coupons),
            "sales": len(sales_rows),
        },
    }


def admin_set_shop_banner_active(session: Session, banner_id: int, shop_user_id: int, is_active: bool) -> Banner:
    b = session.get(Banner, banner_id)
    if not b or b.shop_user_id != shop_user_id:
        raise NotFoundError("Banner not found")
    b.is_active = bool(is_active)
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


def admin_set_shop_coupon_active(session: Session, coupon_id: int, shop_user_id: int, is_active: bool) -> Coupon:
    c = session.get(Coupon, coupon_id)
    if not c or c.shop_user_id != shop_user_id:
        raise NotFoundError("Offer not found")
    c.is_active = bool(is_active)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def update_sales_status(session: Session, user: User, order_id: int, status: str, note: str | None = None) -> dict:
    _selling_shop(session, user)
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
    # Customer inbox ping
    session.add(
        Notification(
            user_id=order.user_id,
            type=NotificationType.ORDER,
            title=f"Order {order.order_number}",
            body=f"Status updated to {new_status.value.replace('_', ' ')}",
            data={"order_id": order.id, "status": new_status.value},
        )
    )
    session.commit()
    session.refresh(order)
    payload = {
        "status": new_status.value,
        "user_id": order.user_id,
        "shop_user_id": order.shop_user_id,
        "order_number": order.order_number,
    }
    emit_order_status(order.id, payload)
    emit_user_event(user.id, "sales_order_update", {"order_id": order.id, **payload})
    return _order_dict(session, order)
