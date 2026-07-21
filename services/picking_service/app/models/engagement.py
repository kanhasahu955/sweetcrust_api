"""Wallet, loyalty, referral, subscriptions, corporate, share-track."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from package.common.utils import utc_now

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class WalletAccount(SQLModel, table=True):
    __tablename__ = "wallet_accounts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    balance: float = Field(default=0.0)
    updated_at: datetime = Field(default_factory=utc_now)


class WalletTxn(SQLModel, table=True):
    __tablename__ = "wallet_txns"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    amount: float = Field(default=0.0)
    txn_type: str = Field(default="credit", max_length=40)
    title: str = Field(max_length=200)
    subtitle: Optional[str] = Field(default=None, max_length=200)
    balance_after: float = Field(default=0.0)
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id")
    created_at: datetime = Field(default_factory=utc_now)


class LoyaltyAccount(SQLModel, table=True):
    __tablename__ = "loyalty_accounts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    points: int = Field(default=0)
    lifetime_points: int = Field(default=0)
    updated_at: datetime = Field(default_factory=utc_now)


class ReferralCode(SQLModel, table=True):
    __tablename__ = "referral_codes"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    code: str = Field(unique=True, index=True, max_length=32)
    reward_amount: float = Field(default=100.0)
    referred_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)


class SubscriptionPlan(SQLModel, table=True):
    __tablename__ = "subscription_plans"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=120)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    product_id: Optional[int] = Field(default=None, foreign_key="products.id")
    price: float = Field(default=0.0)
    cadence: str = Field(default="weekly", max_length=40)
    is_active: bool = Field(default=True)


class UserSubscription(SQLModel, table=True):
    __tablename__ = "user_subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    plan_id: int = Field(foreign_key="subscription_plans.id", index=True)
    status: str = Field(default="active", max_length=40)
    next_delivery_date: Optional[date] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)


class CorporateInquiry(SQLModel, table=True):
    __tablename__ = "corporate_inquiries"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    company_name: str = Field(max_length=200)
    contact_name: str = Field(max_length=120)
    phone: str = Field(max_length=20)
    email: Optional[str] = Field(default=None, max_length=200)
    headcount: Optional[int] = Field(default=None)
    occasion: Optional[str] = Field(default=None, max_length=120)
    budget: Optional[float] = Field(default=None)
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    status: str = Field(default="submitted", max_length=40)
    created_at: datetime = Field(default_factory=utc_now)


class ShareTrackLink(SQLModel, table=True):
    __tablename__ = "share_track_links"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    token: str = Field(unique=True, index=True, max_length=64)
    expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
