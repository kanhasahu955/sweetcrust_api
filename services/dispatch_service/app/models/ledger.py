"""Shop credit ledger + admin purchases from wholesaler shops."""
from datetime import datetime
from typing import Optional

from package.common.utils import utc_now
from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class CreditLedgerEntry(SQLModel, table=True):
    __tablename__ = "credit_ledger_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    retailer_user_id: int = Field(foreign_key="users.id", index=True)
    entry_type: str = Field(index=True, max_length=20)  # debit | credit | adjustment
    amount: float = Field(default=0.0)
    balance_after: float = Field(default=0.0)
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id", index=True)
    payment_id: Optional[int] = Field(default=None, foreign_key="payments.id", index=True)
    note: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=utc_now)


class SupplierPurchase(SQLModel, table=True):
    __tablename__ = "supplier_purchases"

    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_user_id: int = Field(foreign_key="users.id", index=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    product_name: str = Field(max_length=200)
    qty: int = Field(default=1)
    unit_cost: float = Field(default=0.0)
    total: float = Field(default=0.0)
    status: str = Field(default="received", max_length=20, index=True)
    paid_amount: float = Field(default=0.0)
    paid_at: Optional[datetime] = Field(default=None)
    pay_method: Optional[str] = Field(default=None, max_length=40)
    note: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
