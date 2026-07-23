"""Retailer billing hub: owe bakery (B2B) + bakery owes me (supplier POs)."""
from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session, select

from app.models.commerce import Invoice, Order, OrderItem, Payment
from app.models.enums import NotificationType, OrderStatus, OrderType, PaymentStatus
from app.models.ops import Notification
from app.models.user import RetailerProfile, User
from app.services import credit as credit_ops
from app.services import purchases as purchase_ops
from app.services import sell as sell_ops
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
    pending_sales = len(
        list(
            session.exec(
                select(Order).where(
                    Order.shop_user_id == user.id,
                    Order.status == OrderStatus.PLACED,
                )
            ).all()
        )
    )
    # You owe bakery = khata + unpaid B2B. Bakery owes you = payable (heal with open PO dues).
    you_owe = round(outstanding + unpaid_due, 2)
    owes_you = round(max(payable, pending_po_due), 2)
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
        "you_owe": you_owe,
        "owes_you": owes_you,
        "net_position": round(owes_you - you_owe, 2),
        "pending_sales": pending_sales,
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
    """All invoices for this shop: subscription, B2B buy, customer sales, supplier settlements."""
    from sqlalchemy import and_, or_

    from app.services import invoices as invoice_ops

    _profile(session, user)
    out: list[dict] = []
    seen_inv: set[int] = set()
    seen_order: set[int] = set()

    # Invoice rows where this shop is buyer or seller (new template path)
    inv_rows = list(
        session.exec(
            select(Invoice)
            .where(or_(Invoice.buyer_user_id == user.id, Invoice.seller_user_id == user.id))
            .order_by(Invoice.created_at.desc())
            .limit(150)
        ).all()
    )
    for inv in inv_rows:
        if inv.id is None or inv.id in seen_inv:
            continue
        seen_inv.add(inv.id)
        order = session.get(Order, inv.order_id) if inv.order_id else None
        if order:
            seen_order.add(order.id)
        out.append(invoice_ops.invoice_list_row(inv, order=order))

    # Legacy / draft: B2B bakery→shop orders + customer sales at this shop
    orders = list(
        session.exec(
            select(Order)
            .where(
                or_(
                    and_(Order.user_id == user.id, Order.order_type == OrderType.B2B_SHOP_ORDER.value),
                    Order.shop_user_id == user.id,
                )
            )
            .order_by(Order.created_at.desc())
            .limit(100)
        ).all()
    )
    for order in orders:
        if order.id in seen_order:
            continue
        inv = session.exec(select(Invoice).where(Invoice.order_id == order.id)).first()
        if inv and inv.id is not None and inv.id not in seen_inv:
            seen_inv.add(inv.id)
            seen_order.add(order.id)
            out.append(invoice_ops.invoice_list_row(inv, order=order))
            continue
        if inv:
            continue
        items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
        ot = order.order_type.value if hasattr(order.order_type, "value") else str(order.order_type or "")
        is_b2b = ot == OrderType.B2B_SHOP_ORDER.value
        seen_order.add(order.id)
        out.append(
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "invoice_number": None,
                "invoice_id": None,
                "kind": invoice_ops.KIND_B2B if is_b2b else invoice_ops.KIND_CUSTOMER,
                "template": invoice_ops.TEMPLATE_PRODUCT,
                "title": f"{'Wholesale' if is_b2b else 'Sale'} · {order.order_number}",
                "payment_status": order.payment_status.value
                if hasattr(order.payment_status, "value")
                else order.payment_status,
                "payment_method": order.payment_method.value
                if order.payment_method and hasattr(order.payment_method, "value")
                else order.payment_method,
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

    out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return out[:150]


def supplier_bills(session: Session, user: User) -> list[dict]:
    profile = _profile(session, user)
    if not profile.is_wholesaler:
        return []
    return purchase_ops.list_purchases(session, supplier_user_id=user.id)


def pay_udhaar(session: Session, user: User, data: dict) -> dict:
    """Shop records a payment against bakery udhaar (Khatabook-style Jama)."""
    amount = float(data.get("amount") or 0)
    method = (data.get("method") or "upi").strip().lower() or "upi"
    note = (data.get("note") or "").strip() or None
    if method not in ("upi", "cash", "bank", "razorpay", "other"):
        method = "upi"
    return credit_ops.credit_payment(
        session,
        user.id,
        amount,
        note=note,
        method=method,
        created_by=user.id,
    )


def payment_history(session: Session, user: User) -> dict:
    """All money movements with purpose: subscription, admin PO, customer, bakery, dues."""
    profile = _profile(session, user)
    entries: list[dict] = []

    def _add(
        *,
        eid: str,
        source: str,
        purpose: str,
        title: str,
        amount: float,
        direction: str,
        status: str,
        created_at: str | None,
        note: str | None = None,
        lines: list | None = None,
        extra: dict | None = None,
    ) -> None:
        day = (created_at or "")[:10] or None
        row = {
            "id": eid,
            "source": source,
            "purpose": purpose,
            "kind": purpose,
            "title": title,
            "amount": round(float(amount or 0), 2),
            "direction": direction,
            "status": status,
            "note": note,
            "created_at": created_at,
            "day": day,
            "lines": lines or [],
        }
        if extra:
            row.update(extra)
        entries.append(row)

    # Sell subscription payments (from activation notifications)
    sub_notes = list(
        session.exec(
            select(Notification)
            .where(Notification.user_id == user.id, Notification.type == NotificationType.PAYMENT)
            .order_by(Notification.created_at.desc())
            .limit(50)
        ).all()
    )
    saw_sub = False
    for n in sub_notes:
        data = n.data if isinstance(n.data, dict) else {}
        if data.get("kind") != "sell_subscription" and data.get("purpose") != "subscription":
            continue
        saw_sub = True
        when = data.get("paid_at") or (n.created_at.isoformat() if n.created_at else None)
        _add(
            eid=f"sub-{n.id}",
            source="subscription",
            purpose="subscription",
            title=n.title or "Sell subscription",
            amount=float(data.get("amount") or 0),
            direction="out",
            status="paid",
            created_at=when,
            note=n.body,
            extra={"cadence": data.get("cadence"), "expires_at": data.get("expires_at")},
        )

    # Fallback: show current plan if active but no history row yet
    if not saw_sub and (profile.sell_subscription_status or "") == "approved":
        exp = profile.sell_subscription_expires_at
        when = exp.isoformat() if exp else None
        prices = sell_ops._plan_prices(session)
        cadence = (profile.sell_plan or "monthly").lower()
        amt = prices.get(cadence) or prices.get("monthly") or 0
        _add(
            eid="sub-current",
            source="subscription",
            purpose="subscription",
            title=f"Sell plan · {cadence}",
            amount=float(amt),
            direction="out",
            status="active",
            created_at=when,
            note=f"Active until {exp.date().isoformat()}" if exp else "Active sell plan",
            extra={"cadence": cadence, "expires_at": when},
        )

    # Bakery khata ledger
    for e in credit_ops.list_ledger(session, user.id, limit=200):
        et = str(e.entry_type or "").lower()
        if et not in ("credit", "debit"):
            continue
        is_pay = et == "credit"
        _add(
            eid=f"ledger-{e.id}",
            source="bakery",
            purpose="bakery_payment" if is_pay else "bakery_bill",
            title="Paid to bakery" if is_pay else "Bakery bill (udhaar)",
            amount=float(e.amount or 0),
            direction="out" if is_pay else "due",
            status="paid" if is_pay else "due",
            created_at=e.created_at.isoformat() if e.created_at else None,
            note=e.note,
            extra={"balance_after": float(e.balance_after or 0), "order_id": e.order_id},
        )

    # Admin PO: paid + open dues
    for p in purchase_ops.list_purchases(session, supplier_user_id=user.id):
        paid = float(p.get("paid_amount") or 0)
        due = float(p.get("due") or 0)
        total = float(p.get("total") or 0)
        bill = str(p.get("bill_no") or f"SP-{p.get('id')}")
        lines = p.get("lines") or []
        if paid > 0:
            _add(
                eid=f"po-paid-{p.get('id')}",
                source="admin",
                purpose="admin_payment",
                title=f"Admin paid · {bill}",
                amount=paid,
                direction="in",
                status="paid" if due <= 0.001 else "partial",
                created_at=p.get("paid_at") or p.get("created_at"),
                note=str(p.get("pay_method") or "admin"),
                lines=lines,
                extra={"bill_no": bill, "product_name": p.get("product_name"), "due": due},
            )
        if due > 0.001 and str(p.get("status") or "") != "rejected":
            _add(
                eid=f"po-due-{p.get('id')}",
                source="admin",
                purpose="admin_due",
                title=f"Due from bakery · {bill}",
                amount=due,
                direction="due_in",
                status="due",
                created_at=p.get("created_at"),
                note=str(p.get("product_name") or ""),
                lines=lines,
                extra={"bill_no": bill, "total": total, "paid_amount": paid},
            )

    # Customer order payments
    shop_orders = list(
        session.exec(
            select(Order)
            .where(Order.shop_user_id == user.id)
            .order_by(Order.created_at.desc())
            .limit(100)
        ).all()
    )
    for order in shop_orders:
        items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all())
        lines = [
            {
                "product_name": i.product_name,
                "qty": i.quantity,
                "unit_price": float(i.unit_price or 0),
                "line_total": float(i.total_price or 0),
            }
            for i in items
        ]
        pays = list(
            session.exec(
                select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at.desc())
            ).all()
        )
        for pay in pays:
            st = pay.status.value if hasattr(pay.status, "value") else str(pay.status or "")
            st_l = st.lower()
            if st_l in ("pending", "failed", "cancelled"):
                continue
            when = pay.paid_at or pay.created_at
            method = pay.method.value if pay.method and hasattr(pay.method, "value") else pay.method
            _add(
                eid=f"pay-{pay.id}",
                source="customer",
                purpose="customer_payment",
                title=f"Customer paid · {order.order_number}",
                amount=float(pay.amount or 0),
                direction="in",
                status="paid",
                created_at=when.isoformat() if when else None,
                note=str(method or ""),
                lines=lines,
                extra={"order_id": order.id, "order_number": order.order_number},
            )

    # Open bakery udhaar summary (if any)
    outstanding = float(profile.outstanding_balance or 0)
    if outstanding > 0.001:
        _add(
            eid="due-bakery-outstanding",
            source="bakery",
            purpose="bakery_due",
            title="Outstanding to bakery",
            amount=outstanding,
            direction="due",
            status="due",
            created_at=None,
            note=f"Credit left ₹{max(0.0, float(profile.credit_limit or 0) - outstanding):.0f}",
        )

    entries.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    by_day: dict[str, list[dict]] = defaultdict(list)
    day_totals: dict[str, float] = defaultdict(float)
    for e in entries:
        day = e.get("day") or "open"
        by_day[day].append(e)
        if e.get("direction") == "in":
            day_totals[day] += float(e.get("amount") or 0)
        elif e.get("direction") == "out":
            day_totals[day] -= float(e.get("amount") or 0)

    def _day_key(d: str) -> str:
        return "0000-00-00" if d == "open" else d

    days = [
        {
            "date": day,
            "net": round(day_totals[day], 2),
            "count": len(by_day[day]),
            "entries": by_day[day],
        }
        for day in sorted(by_day.keys(), key=_day_key, reverse=True)
    ]

    money_in = round(sum(float(e["amount"]) for e in entries if e["direction"] == "in"), 2)
    money_out = round(sum(float(e["amount"]) for e in entries if e["direction"] == "out"), 2)
    totals = {
        "in": money_in,
        "out": money_out,
        "cash_net": round(money_in - money_out, 2),
        "dues": round(
            sum(float(e["amount"]) for e in entries if e["direction"] in ("due", "due_in")),
            2,
        ),
        "subscription": round(
            sum(float(e["amount"]) for e in entries if e["purpose"] == "subscription"),
            2,
        ),
    }
    return {"days": days, "entries": entries, "total_entries": len(entries), "totals": totals}


def dashboard(session: Session, user: User) -> dict:
    """Retailer billing dashboard: balances, dues, subscription, recent money."""
    profile = _profile(session, user)
    bill = summary(session, user)
    hist = payment_history(session, user)
    sub_status = getattr(profile, "sell_subscription_status", None) or "none"
    exp = getattr(profile, "sell_subscription_expires_at", None)
    recent = (hist.get("entries") or [])[:8]
    open_dues = [e for e in hist.get("entries") or [] if e.get("direction") in ("due", "due_in")][:6]
    totals = hist.get("totals") or {}
    return {
        **bill,
        "subscription": {
            "status": sub_status,
            "plan": getattr(profile, "sell_plan", None),
            "expires_at": exp.isoformat() if exp else None,
            "can_sell": profile.approval_status == "approved"
            and sub_status == "approved"
            and not profile.is_blocked,
        },
        "totals": totals,
        # Hero figure: cash movement (in − out). Balance sheet lives in you_owe / owes_you.
        "cash_net": float(totals.get("cash_net") or 0),
        "recent": recent,
        "open_dues": open_dues,
        "shop_name": profile.shop_name,
    }


def pending_sales_count(session: Session, user: User) -> dict:
    n = len(
        list(
            session.exec(
                select(Order).where(
                    Order.shop_user_id == user.id,
                    Order.status == OrderStatus.PLACED,
                )
            ).all()
        )
    )
    return {"pending": n}


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
