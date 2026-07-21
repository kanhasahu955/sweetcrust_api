"""Assert pending PO → accept bumps stock; reject leaves stock unchanged.

Run from repo:
  cd backend_v2 && PYTHONPATH=$PWD:$PWD/services/store_ops_service .venv/bin/python \
    services/store_ops_service/check_supplier_po.py
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
load_dotenv(os.path.join(ROOT, ".env"))
sys.path[:0] = [ROOT, os.path.join(ROOT, "services", "store_ops_service")]

from sqlalchemy import create_engine  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.models.catalog import Product  # noqa: E402
from app.models.ledger import SupplierPurchase  # noqa: E402
from app.models.user import RetailerProfile  # noqa: E402
from app.services import purchases as purchase_ops  # noqa: E402


def _engine():
    url = os.environ["DATABASE_URL"].replace("+aiomysql", "").replace("+asyncmy", "")
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[8:]
    return create_engine(url)


def main() -> None:
    eng = _engine()
    with Session(eng) as session:
        profile = session.exec(
            select(RetailerProfile).where(RetailerProfile.is_wholesaler == True)  # noqa: E712
        ).first()
        assert profile, "need a wholesaler shop"
        product = session.exec(select(Product).limit(1)).first()
        assert product, "need a product"
        before = int(product.stock_qty or 0)

        pending = purchase_ops.create_purchase(
            session,
            supplier_user_id=profile.user_id,
            product_id=product.id,
            qty=2,
            unit_cost=5.0,
            note="check_supplier_po pending",
            created_by=1,
        )
        assert pending["status"] == "pending", pending
        mid = session.get(Product, product.id)
        assert int(mid.stock_qty or 0) == before, "pending must not bump stock"

        accepted = purchase_ops.accept_purchase(session, pending["id"], profile.user_id)
        assert accepted["status"] == "received", accepted
        after = session.get(Product, product.id)
        assert int(after.stock_qty or 0) == before + 2, (before, after.stock_qty)

        # reject path
        pending2 = purchase_ops.create_purchase(
            session,
            supplier_user_id=profile.user_id,
            product_id=product.id,
            qty=3,
            unit_cost=1.0,
            note="check_supplier_po reject",
            created_by=1,
        )
        stock_before_reject = int(session.get(Product, product.id).stock_qty or 0)
        rejected = purchase_ops.reject_purchase(session, pending2["id"], profile.user_id)
        assert rejected["status"] == "rejected", rejected
        assert int(session.get(Product, product.id).stock_qty or 0) == stock_before_reject

        # cleanup test rows + undo accept side effects
        for pid in (pending["id"], pending2["id"]):
            row = session.get(SupplierPurchase, pid)
            if row:
                session.delete(row)
        p = session.get(Product, product.id)
        p.stock_qty = before
        session.add(p)
        prof = session.get(RetailerProfile, profile.id)
        if prof:
            prof.payable_balance = max(0.0, round(float(prof.payable_balance or 0) - float(accepted["total"]), 2))
            session.add(prof)
        session.commit()
    print("OK supplier PO pending→accept / reject")


if __name__ == "__main__":
    main()
