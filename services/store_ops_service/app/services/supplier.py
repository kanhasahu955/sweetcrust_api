"""Wholesaler shop self-service: POs, offer qty/cost, payouts."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.catalog import Product
from app.models.ledger import SupplierPurchase
from app.models.user import RetailerProfile, User
from app.services import purchases as purchase_ops
from package.common.errors import BadRequestError, ForbiddenError, NotFoundError
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def _wholesaler_profile(session: Session, user: User) -> RetailerProfile:
    profile = session.exec(select(RetailerProfile).where(RetailerProfile.user_id == user.id)).first()
    if not profile:
        raise NotFoundError("Shop profile not found")
    if not profile.is_wholesaler:
        raise ForbiddenError("Shop is not marked as supplier/wholesaler")
    return profile


def summary(session: Session, user: User) -> dict:
    profile = _wholesaler_profile(session, user)
    pending = session.exec(
        select(SupplierPurchase).where(
            SupplierPurchase.supplier_user_id == user.id,
            SupplierPurchase.status == "pending",
        )
    ).all()
    return {
        "is_wholesaler": True,
        "shop_name": profile.shop_name,
        "payable_balance": float(profile.payable_balance or 0),
        "pending_count": len(list(pending)),
        "upi_id": profile.upi_id,
    }


def list_my_purchases(session: Session, user: User) -> list[dict]:
    _wholesaler_profile(session, user)
    return purchase_ops.list_purchases(session, supplier_user_id=user.id)


def accept(session: Session, user: User, purchase_id: int) -> dict:
    _wholesaler_profile(session, user)
    return purchase_ops.accept_purchase(session, purchase_id, user.id)


def reject(session: Session, user: User, purchase_id: int) -> dict:
    _wholesaler_profile(session, user)
    return purchase_ops.reject_purchase(session, purchase_id, user.id)


def _product_offer_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "brand_name": p.brand_name,
        "unit_label": p.unit_label,
        "purchase_cost": p.purchase_cost,
        "supplier_available_qty": int(getattr(p, "supplier_available_qty", 0) or 0),
        "warehouse_stock_qty": int(p.stock_qty or 0),
        "is_active": p.is_active,
        "is_draft": p.is_draft,
        "cover_image_url": p.cover_image_url,
    }


def list_my_products(session: Session, user: User) -> list[dict]:
    _wholesaler_profile(session, user)
    rows = session.exec(
        select(Product).where(Product.supplier_user_id == user.id).order_by(Product.name)
    ).all()
    return [_product_offer_dict(p) for p in rows]


def patch_my_product(
    session: Session,
    user: User,
    product_id: int,
    *,
    supplier_available_qty: int | None = None,
    purchase_cost: float | None = None,
) -> dict:
    _wholesaler_profile(session, user)
    product = session.get(Product, product_id)
    if not product or product.supplier_user_id != user.id:
        raise NotFoundError("Product not found")
    if supplier_available_qty is not None:
        if supplier_available_qty < 0:
            raise BadRequestError("supplier_available_qty must be >= 0")
        product.supplier_available_qty = int(supplier_available_qty)
    if purchase_cost is not None:
        if purchase_cost < 0:
            raise BadRequestError("purchase_cost must be >= 0")
        product.purchase_cost = float(purchase_cost)
    product.updated_at = utc_now()
    session.add(product)
    session.commit()
    session.refresh(product)
    logger.info("supplier %s updated offer product %s", user.id, product_id)
    return _product_offer_dict(product)
