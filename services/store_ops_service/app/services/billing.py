"""Retailer billing hub: owe bakery (B2B) + bakery owes me (supplier POs)."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.commerce import Invoice, Order, OrderItem
from app.models.enums import OrderType, PaymentStatus
from app.models.user import RetailerProfile, User
from app.services import credit as credit_ops
from app.services import purchases as purchase_ops
from package.common.errors import NotFoundError


def _profile(session: Session, user: User) -> RetailerProfile:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user.id)).first()
    if not profile:
        raise NotFoundError("Shop profile not found")
    return profile


def summary(session: Session, user: User) -> dict:
    profile = _profile(session, user)
    outstanding = float(profile.outstanding_balance or 0)
    limit = float(profile.credit_limit or 0)
    payable = float(profile.payable_balance or 0)
    purchases = purchase_ops.list_purchases(session, supplier_user_id=user.id) if profile.is_wholesaler else []
    pending_po_due = round(sum(float(p.get("due") or 0) for p in purchases if p.get("status") in ("received", "partial")), 2)
    unpaid_orders = list(
        session.exec(
            select(Order).where(
                Order.user_id == user.id,
                Order.order_type == OrderType.B2B_SHOP_ORDER.value,
                Order.payment_status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIALLY_PAID, PaymentStatus.PROCESSING]),
            )
        ).all()
    )
    unpaid_due = round(
        sum(
            max(0.0, float(o.final_amount or 0) - float(getattr(o, "paid_amount", 0) or 0))
            for o in unpaid_orders
        ),
        2,
    )
    return {
        "shop_name": profile.shop_name,
        "is_wholesaler": bool(profile.is_wholesaler),
        # Shop owes bakery (udhaar)
        "outstanding_balance": outstanding,
        "credit_limit": limit,
        "credit_remaining": max(0.0, round(limit - outstanding, 2)),
        "unpaid_b2b_orders": len(unpaid_orders),
        "unpaid_b2b_amount": unpaid_due,
        # Bakery owes shop (supplier)
        "payable_balance": payable,
        "supplier_due": pending_po_due,
        "net_position": round(payable - outstanding, 2),
    }


def ledger(session: Session, user: User, limit: int = 100) -> list[dict]:
    _profile(session, user)
    rows = credit_ops.list_ledger(session, user.id, limit=limit)
    return [
        {
            "id": e.id,
            "entry_type": e.entry_type,
            "amount": e.amount,
            "balance_after": e.balance_after,
            "order_id": e.order_id,
            "payment_id": e.payment_id,
            "note": e.note,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


def invoices(session: Session, user: User) -> list[dict]:
    _profile(session, user)
    orders = list(
        session.exec(
            select(Order)
            .where(Order.user_id == user.id, Order.order_type == OrderType.B2B_SHOP_ORDER.value)
            .order_by(Order.created_at.desc())
            .limit(100)
        ).all()
    )
    out = []
    for order in orders:
        inv = session.exec(select(Invoice).where(Invoice.order_id == order.id)).first()
        items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
        out.append(
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "invoice_number": inv.invoice_number if inv else None,
                "invoice_id": inv.id if inv else None,
                "payment_status": order.payment_status.value if hasattr(order.payment_status, "value") else order.payment_status,
                "payment_method": order.payment_method.value if order.payment_method and hasattr(order.payment_method, "value") else order.payment_method,
                "subtotal": order.subtotal,
                "gst_amount": order.gst_amount,
                "final_amount": order.final_amount,
                "paid_amount": float(getattr(order, "paid_amount", 0) or 0),
                "due": round(
                    max(0.0, float(order.final_amount or 0) - float(getattr(order, "paid_amount", 0) or 0)),
                    2,
                ),
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "lines": [
                    {
                        "product_name": i.product_name,
                        "qty": i.quantity,
                        "unit_price": i.unit_price,
                        "line_total": i.total_price,
                    }
                    for i in items
                ],
            }
        )
    return out


def supplier_bills(session: Session, user: User) -> list[dict]:
    profile = _profile(session, user)
    if not profile.is_wholesaler:
        return []
    return purchase_ops.list_purchases(session, supplier_user_id=user.id)


def admin_shop_account(session: Session, retailer_user_id: int) -> dict:
    """Full shop account for admin drawer: orders, billing maths, ledger, supplier POs."""
    user = session.get(User, retailer_user_id)
    if not user:
        raise NotFoundError("Shop not found")
    profile = _profile(session, user)
    bill_summary = summary(session, user)
    order_rows = invoices(session, user)
    ledger_rows = ledger(session, user, limit=100)
    po_rows = supplier_bills(session, user)

    billed = round(sum(float(o.get("final_amount") or 0) for o in order_rows), 2)
    collected = round(sum(float(o.get("paid_amount") or 0) for o in order_rows), 2)
    order_due = round(sum(float(o.get("due") or 0) for o in order_rows), 2)
    gst_total = round(sum(float(o.get("gst_amount") or 0) for o in order_rows), 2)
    subtotal = round(sum(float(o.get("subtotal") or 0) for o in order_rows), 2)

    collections = [e for e in ledger_rows if str(e.get("entry_type") or "").lower() == "credit"]
    debits = [e for e in ledger_rows if str(e.get("entry_type") or "").lower() == "debit"]
    collected_ledger = round(sum(float(e.get("amount") or 0) for e in collections), 2)
    debited_ledger = round(sum(float(e.get("amount") or 0) for e in debits), 2)

    return {
        "user_id": retailer_user_id,
        "shop_name": profile.shop_name,
        "owner_name": profile.owner_name,
        "summary": bill_summary,
        "totals": {
            "orders": len(order_rows),
            "subtotal": subtotal,
            "gst": gst_total,
            "billed": billed,
            "paid_on_orders": collected,
            "order_due": order_due,
            "outstanding_balance": float(profile.outstanding_balance or 0),
            "credit_limit": float(profile.credit_limit or 0),
            "credit_remaining": bill_summary["credit_remaining"],
            "payable_balance": float(profile.payable_balance or 0),
            "ledger_debits": debited_ledger,
            "ledger_collections": collected_ledger,
            "net_position": bill_summary["net_position"],
        },
        "orders": order_rows,
        "ledger": ledger_rows,
        "supplier_bills": po_rows,
    }
