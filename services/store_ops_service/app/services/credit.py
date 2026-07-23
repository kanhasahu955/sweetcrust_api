"""Shop udhaar / credit ledger."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.commerce import Order, Payment
from app.models.enums import CreditEntryType, OrderType, PaymentStatus
from app.models.ledger import CreditLedgerEntry
from app.models.user import RetailerProfile, User
from app.producers.events import emit_admin_event
from package.common.errors import BadRequestError, ForbiddenError, NotFoundError
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def get_profile(session: Session, user_id: int) -> RetailerProfile:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user_id)).first()
    if not profile:
        raise NotFoundError("Shop profile not found")
    return profile


def debit_credit(
    session: Session,
    user: User,
    amount: float,
    *,
    order_id: int | None = None,
    note: str | None = None,
    created_by: int | None = None,
) -> CreditLedgerEntry:
    if amount <= 0:
        raise BadRequestError("Debit amount must be positive")
    profile = get_profile(session, user.id)
    if profile.is_blocked:
        raise ForbiddenError("Shop is blocked")
    if not profile.credit_allowed:
        raise BadRequestError("Credit not allowed for this shop")
    projected = round(profile.outstanding_balance + amount, 2)
    if projected > profile.credit_limit:
        raise BadRequestError(
            f"Order ₹{amount:.0f} would exceed credit limit "
            f"(outstanding ₹{profile.outstanding_balance:.0f} / limit ₹{profile.credit_limit:.0f})"
        )
    profile.outstanding_balance = projected
    entry = CreditLedgerEntry(
        retailer_user_id=user.id,
        entry_type=CreditEntryType.DEBIT.value,
        amount=round(amount, 2),
        balance_after=projected,
        order_id=order_id,
        note=note or "B2B credit order",
        created_by=created_by or user.id,
    )
    session.add(profile)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def _allocate_collection_to_orders(session: Session, retailer_user_id: int, amount: float) -> list[int]:
    """FIFO: apply collection to oldest unpaid/partial B2B orders (supports partial pay)."""
    remaining = round(amount, 2)
    touched_ids: list[int] = []
    orders = list(
        session.exec(
            select(Order)
            .where(
                Order.user_id == retailer_user_id,
                Order.order_type == OrderType.B2B_SHOP_ORDER.value,
                Order.payment_status.in_(
                    [PaymentStatus.PENDING, PaymentStatus.PARTIALLY_PAID, PaymentStatus.PROCESSING]
                ),
            )
            .order_by(Order.created_at.asc())
        ).all()
    )
    for order in orders:
        if remaining <= 0.001:
            break
        total = round(float(order.final_amount or 0), 2)
        already = round(float(getattr(order, "paid_amount", 0) or 0), 2)
        due = round(total - already, 2)
        if due <= 0.001:
            continue
        apply = round(min(remaining, due), 2)
        order.paid_amount = round(already + apply, 2)
        if order.paid_amount + 0.001 >= total:
            order.payment_status = PaymentStatus.PAID
        else:
            order.payment_status = PaymentStatus.PARTIALLY_PAID
        order.updated_at = utc_now()
        session.add(order)
        pay = session.exec(select(Payment).where(Payment.order_id == order.id).order_by(Payment.id.desc())).first()
        if pay:
            pay.amount = float(order.paid_amount)
            pay.status = order.payment_status
            session.add(pay)
        touched_ids.append(int(order.id))
        remaining = round(remaining - apply, 2)
    return touched_ids


def credit_payment(
    session: Session,
    retailer_user_id: int,
    amount: float,
    *,
    note: str | None = None,
    method: str | None = None,
    created_by: int | None = None,
    payment_id: int | None = None,
) -> dict:
    if amount <= 0:
        raise BadRequestError("Collection amount must be positive")
    profile = get_profile(session, retailer_user_id)
    owed = round(float(profile.outstanding_balance or 0), 2)
    pay = round(float(amount), 2)
    if pay > owed + 0.01:
        raise BadRequestError(f"Amount ₹{pay:.0f} exceeds receivable ₹{owed:.0f}")
    new_bal = round(max(0.0, owed - pay), 2)
    profile.outstanding_balance = new_bal
    allocated = _allocate_collection_to_orders(session, retailer_user_id, pay)
    label = f"Collection ({method})" if method else "Collection"
    if allocated:
        label = f"{label} · orders {','.join(str(i) for i in allocated)}"
    entry = CreditLedgerEntry(
        retailer_user_id=retailer_user_id,
        entry_type=CreditEntryType.CREDIT.value,
        amount=pay,
        balance_after=new_bal,
        payment_id=payment_id,
        note=(note or label),
        created_by=created_by,
    )
    session.add(profile)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    # Each settled B2B order gets a product invoice (idempotent).
    if allocated:
        try:
            from app.services import invoices as invoice_ops

            for oid in allocated:
                order = session.get(Order, oid)
                if order:
                    invoice_ops.issue_from_order(session, order)
        except Exception:
            logger.exception("B2B invoice on collection failed retailer=%s", retailer_user_id)
    emit_admin_event(
        "shop_collection",
        {
            "user_id": retailer_user_id,
            "amount": pay,
            "outstanding_balance": new_bal,
            "method": method,
        },
    )
    logger.info("collect retailer=%s amount=%s bal=%s orders=%s", retailer_user_id, pay, new_bal, allocated)
    return {
        "id": entry.id,
        "entry_type": "credit",
        "amount": pay,
        "balance_after": new_bal,
        "outstanding_balance": new_bal,
        "order_ids": allocated,
        "note": entry.note,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def list_ledger(session: Session, retailer_user_id: int, limit: int = 100) -> list[CreditLedgerEntry]:
    return list(
        session.exec(
            select(CreditLedgerEntry)
            .where(CreditLedgerEntry.retailer_user_id == retailer_user_id)
            .order_by(CreditLedgerEntry.created_at.desc())
            .limit(limit)
        ).all()
    )
