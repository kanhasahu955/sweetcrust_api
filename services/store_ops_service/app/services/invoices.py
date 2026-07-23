"""Invoice templates — every paid money movement gets one Invoice row."""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models.commerce import Invoice, Order, OrderItem, Payment
from app.models.enums import OrderType, UserRole
from app.models.ops import BakerySettings
from app.models.user import RetailerProfile, User
from package.common.mail import email_invoice
from package.common.utils import generate_invoice_number
from package.logger import get_logger

logger = get_logger(__name__)

# Visual template families (UI switches on this).
TEMPLATE_SUBSCRIPTION = "subscription_pack"
TEMPLATE_PRODUCT = "product_payment"

KIND_SUBSCRIPTION = "subscription_pack"
KIND_B2B = "b2b_wholesale"
KIND_CUSTOMER = "customer_order"
KIND_SUPPLIER = "supplier_settlement"

_PREFIX = {
    KIND_SUBSCRIPTION: "SUB",
    KIND_B2B: "B2B",
    KIND_CUSTOMER: "INV",
    KIND_SUPPLIER: "SP",
}


def template_for_kind(kind: str) -> str:
    return TEMPLATE_SUBSCRIPTION if kind == KIND_SUBSCRIPTION else TEMPLATE_PRODUCT


def _bakery(session: Session) -> BakerySettings:
    return session.exec(select(BakerySettings)).first() or BakerySettings()


def _find_existing(
    session: Session,
    *,
    order_id: int | None,
    kind: str,
    ref_type: str | None,
    ref_id: str | None,
) -> Invoice | None:
    if order_id is not None:
        row = session.exec(select(Invoice).where(Invoice.order_id == order_id)).first()
        if row:
            return row
    if ref_type and ref_id:
        return session.exec(
            select(Invoice).where(
                Invoice.kind == kind,
                Invoice.ref_type == ref_type,
                Invoice.ref_id == ref_id,
            )
        ).first()
    return None


def issue_invoice(
    session: Session,
    *,
    kind: str,
    items: list[dict[str, Any]],
    grand_total: float,
    customer_name: str,
    customer_phone: str = "",
    customer_address: str | None = None,
    buyer_user_id: int | None = None,
    seller_user_id: int | None = None,
    order_id: int | None = None,
    ref_type: str | None = None,
    ref_id: str | None = None,
    subtotal: float | None = None,
    discount: float = 0.0,
    gst_amount: float = 0.0,
    delivery_fee: float = 0.0,
    payment_method: str | None = None,
    transaction_id: str | None = None,
    notes: str | None = None,
    title: str | None = None,
    meta: dict | None = None,
    commit: bool = True,
) -> Invoice:
    existing = _find_existing(session, order_id=order_id, kind=kind, ref_type=ref_type, ref_id=ref_id)
    if existing:
        return existing

    settings = _bakery(session)
    template = template_for_kind(kind)
    total = round(float(grand_total or 0), 2)
    sub = round(float(subtotal if subtotal is not None else total), 2)
    norm_items = [
        {
            "name": str(i.get("name") or i.get("product_name") or "Item"),
            "qty": float(i.get("qty") or i.get("quantity") or 1),
            "unit_price": float(i.get("unit_price") or 0),
            "total": float(i.get("total") or i.get("line_total") or 0),
        }
        for i in items
    ]
    invoice = Invoice(
        order_id=order_id,
        kind=kind,
        ref_type=ref_type,
        ref_id=ref_id,
        buyer_user_id=buyer_user_id,
        seller_user_id=seller_user_id,
        invoice_number=generate_invoice_number(_PREFIX.get(kind, "INV")),
        bakery_name=settings.bakery_name or "SweetCrust",
        gstin=settings.gstin or "",
        customer_name=(customer_name or "Customer")[:120],
        customer_phone=(customer_phone or "")[:20],
        customer_address=customer_address,
        line_items={
            "template": template,
            "kind": kind,
            "title": title or kind.replace("_", " ").title(),
            "items": norm_items,
            "meta": meta or {},
        },
        subtotal=sub,
        discount=round(float(discount or 0), 2),
        gst_amount=round(float(gst_amount or 0), 2),
        delivery_fee=round(float(delivery_fee or 0), 2),
        grand_total=total,
        payment_method=payment_method,
        transaction_id=transaction_id,
        notes=notes,
    )
    session.add(invoice)
    if commit:
        session.commit()
        session.refresh(invoice)
        _email_new_invoice(session, invoice)
    else:
        session.flush()
    logger.info("invoice %s kind=%s ref=%s/%s", invoice.invoice_number, kind, ref_type, ref_id)
    return invoice


def _email_new_invoice(session: Session, invoice: Invoice) -> None:
    try:
        sent = email_invoice(
            session,
            invoice,
            user_model=User,
            bakery_settings_model=BakerySettings,
            admin_role=UserRole.ADMIN,
        )
        if sent:
            logger.info("invoice %s emailed to %s", invoice.invoice_number, ", ".join(sent))
    except Exception:
        logger.exception("invoice email failed for %s", getattr(invoice, "invoice_number", "?"))


def issue_from_order(session: Session, order: Order, *, commit: bool = True) -> Invoice:
    """Customer sale or B2B bakery→shop product invoice."""
    existing = session.exec(select(Invoice).where(Invoice.order_id == order.id)).first()
    if existing:
        return existing

    ot = order.order_type.value if hasattr(order.order_type, "value") else str(order.order_type or "")
    is_b2b = ot == OrderType.B2B_SHOP_ORDER.value or ot == "b2b_shop_order"
    kind = KIND_B2B if is_b2b else KIND_CUSTOMER
    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
    payment = session.exec(select(Payment).where(Payment.order_id == order.id).order_by(Payment.id.desc())).first()
    addr = order.address_snapshot or {}
    buyer = session.get(User, order.user_id)
    shop = session.get(User, order.shop_user_id) if order.shop_user_id else None
    shop_profile = None
    if order.shop_user_id:
        shop_profile = session.exec(
            select(RetailerProfile).where(RetailerProfile.user_id == order.shop_user_id)
        ).first()

    if is_b2b:
        buyer_profile = session.exec(
            select(RetailerProfile).where(RetailerProfile.user_id == order.user_id)
        ).first()
        customer_name = (
            (buyer_profile.shop_name if buyer_profile else None)
            or (buyer.name if buyer else None)
            or addr.get("shop_name")
            or "Shop"
        )
        seller_user_id = None  # bakery platform
        title = f"Wholesale · {order.order_number}"
        addr_line = (buyer_profile.address_line if buyer_profile else None) or None
    else:
        customer_name = addr.get("full_name") or (buyer.name if buyer else None) or "Customer"
        seller_user_id = order.shop_user_id
        shop_label = (shop_profile.shop_name if shop_profile else None) or (shop.name if shop else None) or "Shop"
        title = f"Sale · {order.order_number} · {shop_label}"
        addr_line = None

    return issue_invoice(
        session,
        kind=kind,
        order_id=order.id,
        ref_type="order",
        ref_id=str(order.id),
        buyer_user_id=order.user_id,
        seller_user_id=seller_user_id,
        customer_name=customer_name,
        customer_phone=order.customer_phone or addr.get("phone") or (buyer.phone if buyer else "") or "",
        customer_address=addr_line
        or ", ".join(
            filter(None, [addr.get("line1") or addr.get("address_line"), addr.get("city"), addr.get("pincode")])
        )
        or None,
        items=[
            {
                "name": i.product_name,
                "qty": i.quantity,
                "unit_price": i.unit_price,
                "total": i.total_price,
            }
            for i in items
        ],
        subtotal=order.subtotal,
        discount=order.discount,
        gst_amount=order.gst_amount,
        delivery_fee=order.delivery_fee,
        grand_total=order.final_amount,
        payment_method=order.payment_method.value if order.payment_method else None,
        transaction_id=payment.transaction_id if payment else None,
        title=title,
        meta={"order_number": order.order_number, "order_type": ot},
        commit=commit,
    )


def issue_subscription(
    session: Session,
    *,
    user: User,
    profile: RetailerProfile,
    cadence: str,
    amount: float,
    payment_ref: str,
    expires_at_iso: str,
) -> Invoice:
    return issue_invoice(
        session,
        kind=KIND_SUBSCRIPTION,
        ref_type="sell_subscription",
        ref_id=payment_ref or f"user-{user.id}-{cadence}-{expires_at_iso}",
        buyer_user_id=user.id,
        seller_user_id=None,
        customer_name=profile.shop_name or user.name or "Shop",
        customer_phone=profile.contact_phone or user.phone or "",
        customer_address=profile.address_line,
        items=[
            {
                "name": f"Sell subscription · {cadence}",
                "qty": 1,
                "unit_price": amount,
                "total": amount,
            }
        ],
        subtotal=amount,
        grand_total=amount,
        payment_method="razorpay",
        transaction_id=payment_ref,
        title=f"Sell plan · {cadence}",
        notes=f"Active until {expires_at_iso[:10]}" if expires_at_iso else None,
        meta={"cadence": cadence, "expires_at": expires_at_iso},
    )


def issue_supplier_payment(
    session: Session,
    *,
    purchase_id: int,
    bill_no: str,
    supplier_user_id: int,
    shop_name: str,
    product_name: str,
    qty: float,
    unit_cost: float,
    pay_amount: float,
    pay_method: str,
    transaction_id: str | None,
    phone: str = "",
) -> Invoice:
    ref = transaction_id or f"po-{purchase_id}-pay-{pay_amount:.2f}"
    return issue_invoice(
        session,
        kind=KIND_SUPPLIER,
        ref_type="supplier_purchase_pay",
        ref_id=ref[:80],
        buyer_user_id=None,  # bakery pays
        seller_user_id=supplier_user_id,
        customer_name=shop_name or "Shop",
        customer_phone=phone,
        items=[
            {
                "name": product_name,
                "qty": qty,
                "unit_price": unit_cost,
                "total": pay_amount,
            }
        ],
        subtotal=pay_amount,
        grand_total=pay_amount,
        payment_method=pay_method,
        transaction_id=transaction_id,
        title=f"Product payment · {bill_no}",
        notes=f"Admin settlement for {bill_no}",
        meta={"purchase_id": purchase_id, "bill_no": bill_no},
    )


def invoice_list_row(inv: Invoice, *, order: Order | None = None, paid_amount: float | None = None) -> dict:
    li = inv.line_items if isinstance(inv.line_items, dict) else {}
    items = li.get("items") or []
    kind = inv.kind or li.get("kind") or KIND_CUSTOMER
    template = li.get("template") or template_for_kind(kind)
    total = float(inv.grand_total or 0)
    paid = float(paid_amount if paid_amount is not None else (total if order is None else float(getattr(order, "paid_amount", 0) or 0)))
    if order is None and kind in (KIND_SUBSCRIPTION, KIND_SUPPLIER):
        paid = total
    due = round(max(0.0, total - paid), 2) if order is not None else 0.0
    pay_status = "paid" if due <= 0.001 else "partial"
    if order is not None:
        ps = order.payment_status
        pay_status = ps.value if hasattr(ps, "value") else str(ps or pay_status)
    return {
        "invoice_id": inv.id,
        "invoice_number": inv.invoice_number,
        "kind": kind,
        "template": template,
        "title": li.get("title") or inv.invoice_number,
        "order_id": inv.order_id or (order.id if order else None),
        "order_number": (order.order_number if order else None) or (li.get("meta") or {}).get("order_number"),
        "payment_status": pay_status,
        "payment_method": inv.payment_method
        or (
            order.payment_method.value
            if order and order.payment_method and hasattr(order.payment_method, "value")
            else (order.payment_method if order else None)
        ),
        "subtotal": inv.subtotal,
        "gst_amount": inv.gst_amount,
        "final_amount": total,
        "paid_amount": paid,
        "due": due,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "buyer_user_id": inv.buyer_user_id,
        "seller_user_id": inv.seller_user_id,
        "transaction_id": inv.transaction_id,
        "notes": inv.notes,
        "lines": [
            {
                "product_name": i.get("name"),
                "qty": i.get("qty"),
                "unit_price": i.get("unit_price"),
                "line_total": i.get("total"),
            }
            for i in items
        ],
    }


# ponytail: tiny self-check; upgrade to pytest if invoice kinds proliferate
if __name__ == "__main__":
    assert template_for_kind(KIND_SUBSCRIPTION) == TEMPLATE_SUBSCRIPTION
    assert template_for_kind(KIND_CUSTOMER) == TEMPLATE_PRODUCT
    assert _PREFIX[KIND_SUBSCRIPTION] == "SUB"
    print("ok")
