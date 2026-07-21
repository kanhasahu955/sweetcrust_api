"""Shop udhaar / credit ledger."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.enums import CreditEntryType
from app.models.ledger import CreditLedgerEntry
from app.models.user import RetailerProfile, User
from package.common.errors import BadRequestError, ForbiddenError, NotFoundError
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


def credit_payment(
    session: Session,
    retailer_user_id: int,
    amount: float,
    *,
    note: str | None = None,
    method: str | None = None,
    created_by: int | None = None,
    payment_id: int | None = None,
) -> CreditLedgerEntry:
    if amount <= 0:
        raise BadRequestError("Collection amount must be positive")
    profile = get_profile(session, retailer_user_id)
    new_bal = round(max(0.0, profile.outstanding_balance - amount), 2)
    profile.outstanding_balance = new_bal
    label = f"Collection ({method})" if method else "Collection"
    entry = CreditLedgerEntry(
        retailer_user_id=retailer_user_id,
        entry_type=CreditEntryType.CREDIT.value,
        amount=round(amount, 2),
        balance_after=new_bal,
        payment_id=payment_id,
        note=note or label,
        created_by=created_by,
    )
    session.add(profile)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    logger.info("collect retailer=%s amount=%s bal=%s", retailer_user_id, amount, new_bal)
    return entry


def list_ledger(session: Session, retailer_user_id: int, limit: int = 100) -> list[CreditLedgerEntry]:
    return list(
        session.exec(
            select(CreditLedgerEntry)
            .where(CreditLedgerEntry.retailer_user_id == retailer_user_id)
            .order_by(CreditLedgerEntry.created_at.desc())
            .limit(limit)
        ).all()
    )
