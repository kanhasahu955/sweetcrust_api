"""Admin buys stock from retailer/wholesaler shops and pays them."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.catalog import Product, StockMovement
from app.models.enums import StockStatus, UserRole
from app.models.ledger import SupplierPurchase
from app.models.user import RetailerProfile, User
from package.common.errors import BadRequestError, ForbiddenError, NotFoundError
from package.common.utils import stock_status_for, utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def _shop(session: Session, supplier_user_id: int) -> tuple[User, RetailerProfile]:
    user = session.get(User, supplier_user_id)
    if not user or user.role != UserRole.RETAILER:
        raise NotFoundError("Shop / wholesaler not found")
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == supplier_user_id)).first()
    if not profile:
        raise NotFoundError("Shop profile not found")
    return user, profile


def purchase_dict(session: Session, p: SupplierPurchase) -> dict:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == p.supplier_user_id)).first()
    product = session.get(Product, p.product_id)
    due = round(float(p.total) - float(p.paid_amount or 0), 2)
    payment_status = "unpaid"
    if p.status == "rejected":
        payment_status = "n/a"
    elif p.status == "pending":
        payment_status = "awaiting_accept"
    elif due <= 0.001:
        payment_status = "paid"
    elif float(p.paid_amount or 0) > 0:
        payment_status = "partial"
    elif p.status in ("received", "partial"):
        payment_status = "pending"
    return {
        "id": p.id,
        "bill_no": f"SP-{p.id:05d}",
        "supplier_user_id": p.supplier_user_id,
        "shop_name": profile.shop_name if profile else None,
        "product_id": p.product_id,
        "product_name": p.product_name,
        "qty": p.qty,
        "unit_cost": p.unit_cost,
        "total": p.total,
        "status": p.status,
        "payment_status": payment_status,
        "paid_amount": p.paid_amount,
        "due": due,
        "paid_at": p.paid_at.isoformat() if p.paid_at else None,
        "pay_method": p.pay_method,
        "note": p.note,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "payable_balance": profile.payable_balance if profile else 0,
        "warehouse_stock_qty": int(product.stock_qty or 0) if product else None,
        "supplier_available_qty": int(getattr(product, "supplier_available_qty", 0) or 0) if product else None,
        "lines": [
            {
                "product_id": p.product_id,
                "product_name": p.product_name,
                "qty": p.qty,
                "unit_cost": p.unit_cost,
                "line_total": p.total,
                "warehouse_stock_qty": int(product.stock_qty or 0) if product else None,
                "supplier_available_qty": int(getattr(product, "supplier_available_qty", 0) or 0) if product else None,
            }
        ],
    }


def _apply_receive(
    session: Session,
    purchase: SupplierPurchase,
    *,
    profile: RetailerProfile,
    created_by: int | None,
    mark_paid: bool = False,
    pay_method: str | None = None,
) -> None:
    """Bump warehouse stock + payable. Call only once when leaving pending."""
    product = session.get(Product, purchase.product_id)
    if not product:
        raise NotFoundError("Product not found")
    qty = int(purchase.qty)
    unit_cost = float(purchase.unit_cost)
    total = float(purchase.total)
    now = utc_now()

    old_qty = int(product.stock_qty or 0)
    old_cost = float(product.purchase_cost or 0)
    new_qty = old_qty + qty
    if new_qty > 0:
        product.purchase_cost = round(((old_cost * old_qty) + (unit_cost * qty)) / new_qty, 2)
    else:
        product.purchase_cost = unit_cost
    product.stock_qty = new_qty
    product.stock_status = StockStatus(stock_status_for(product.stock_qty, product.low_stock_threshold))
    # Offer stock down when bakery receives the PO
    avail = int(getattr(product, "supplier_available_qty", 0) or 0)
    product.supplier_available_qty = max(0, avail - qty)
    product.updated_at = now
    session.add(product)
    session.add(
        StockMovement(
            product_id=product.id,
            change_qty=qty,
            reason="supplier_purchase",
            note=f"From {profile.shop_name}" + (f" — {purchase.note}" if purchase.note else ""),
            created_by=created_by,
        )
    )

    if mark_paid:
        purchase.paid_amount = total
        purchase.paid_at = now
        purchase.pay_method = pay_method
        purchase.status = "paid"
    else:
        purchase.status = "received"
        profile.payable_balance = round(float(profile.payable_balance or 0) + total, 2)
        session.add(profile)

    purchase.updated_at = now
    session.add(purchase)


def create_purchase(
    session: Session,
    *,
    supplier_user_id: int,
    product_id: int,
    qty: int,
    unit_cost: float,
    note: str | None = None,
    created_by: int | None = None,
    mark_paid: bool = False,
    pay_method: str | None = None,
    instant_receive: bool = False,
) -> dict:
    if qty <= 0:
        raise BadRequestError("qty must be > 0")
    if unit_cost < 0:
        raise BadRequestError("unit_cost must be >= 0")
    user, profile = _shop(session, supplier_user_id)
    if not profile.is_wholesaler:
        raise BadRequestError("This shop is not marked as wholesaler/supplier")
    product = session.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")

    total = round(float(unit_cost) * int(qty), 2)
    receive_now = bool(instant_receive or mark_paid)
    purchase = SupplierPurchase(
        supplier_user_id=user.id,
        product_id=product.id,
        product_name=product.name,
        qty=int(qty),
        unit_cost=float(unit_cost),
        total=total,
        status="pending",
        paid_amount=0.0,
        paid_at=None,
        pay_method=None,
        note=note,
        created_by=created_by,
    )
    session.add(purchase)
    session.flush()

    if receive_now:
        _apply_receive(
            session,
            purchase,
            profile=profile,
            created_by=created_by,
            mark_paid=mark_paid,
            pay_method=pay_method if mark_paid else None,
        )

    session.commit()
    session.refresh(purchase)
    logger.info("purchase id=%s supplier=%s total=%s status=%s", purchase.id, supplier_user_id, total, purchase.status)
    return purchase_dict(session, purchase)


def accept_purchase(session: Session, purchase_id: int, supplier_user_id: int) -> dict:
    purchase = session.get(SupplierPurchase, purchase_id)
    if not purchase:
        raise NotFoundError("Purchase not found")
    if purchase.supplier_user_id != supplier_user_id:
        raise ForbiddenError("Not your purchase order")
    if purchase.status != "pending":
        raise BadRequestError(f"Cannot accept purchase in status {purchase.status}")
    _, profile = _shop(session, supplier_user_id)
    _apply_receive(session, purchase, profile=profile, created_by=supplier_user_id, mark_paid=False)
    session.commit()
    session.refresh(purchase)
    return purchase_dict(session, purchase)


def reject_purchase(session: Session, purchase_id: int, supplier_user_id: int) -> dict:
    purchase = session.get(SupplierPurchase, purchase_id)
    if not purchase:
        raise NotFoundError("Purchase not found")
    if purchase.supplier_user_id != supplier_user_id:
        raise ForbiddenError("Not your purchase order")
    if purchase.status != "pending":
        raise BadRequestError(f"Cannot reject purchase in status {purchase.status}")
    purchase.status = "rejected"
    purchase.updated_at = utc_now()
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    return purchase_dict(session, purchase)


def pay_purchase(
    session: Session,
    purchase_id: int,
    *,
    amount: float | None = None,
    pay_method: str = "upi",
    note: str | None = None,
    created_by: int | None = None,
) -> dict:
    purchase = session.get(SupplierPurchase, purchase_id)
    if not purchase:
        raise NotFoundError("Purchase not found")
    if purchase.status not in ("received", "partial"):
        raise BadRequestError("Can only pay received purchase orders")
    due = round(float(purchase.total) - float(purchase.paid_amount or 0), 2)
    if due <= 0:
        raise BadRequestError("Already fully paid")
    pay = round(float(amount if amount is not None else due), 2)
    if pay <= 0 or pay > due + 0.01:
        raise BadRequestError(f"Pay amount must be between 0 and ₹{due:.2f}")

    purchase.paid_amount = round(float(purchase.paid_amount or 0) + pay, 2)
    purchase.paid_at = utc_now()
    purchase.pay_method = pay_method
    purchase.status = "paid" if purchase.paid_amount + 0.001 >= purchase.total else "partial"
    if note:
        purchase.note = ((purchase.note or "") + f" | Paid {pay}: {note}").strip(" |")
    purchase.updated_at = utc_now()
    session.add(purchase)

    _, profile = _shop(session, purchase.supplier_user_id)
    profile.payable_balance = max(0.0, round(float(profile.payable_balance or 0) - pay, 2))
    session.add(profile)
    session.commit()
    session.refresh(purchase)
    _ = created_by
    return purchase_dict(session, purchase)


def list_purchases(session: Session, supplier_user_id: int | None = None) -> list[dict]:
    stmt = select(SupplierPurchase).order_by(SupplierPurchase.created_at.desc()).limit(200)
    if supplier_user_id:
        stmt = stmt.where(SupplierPurchase.supplier_user_id == supplier_user_id)
    rows = list(session.exec(stmt).all())
    return [purchase_dict(session, p) for p in rows]
