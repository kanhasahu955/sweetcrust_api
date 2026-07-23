"""Users AI needs for auth deps + chatbot tools."""
from datetime import datetime
from typing import Optional

from package.common.utils import utc_now

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.models.enums import CustomerSegment, UserRole


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    phone: str = Field(index=True, unique=True, max_length=20)
    name: Optional[str] = Field(default=None, max_length=120)
    email: Optional[str] = Field(default=None, max_length=255, index=True)
    email_verified: bool = Field(default=False)
    password_hash: Optional[str] = Field(default=None, max_length=255)
    role: UserRole = Field(default=UserRole.CUSTOMER, index=True)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    language: str = Field(default="en", max_length=10)
    is_active: bool = Field(default=True)
    is_guest: bool = Field(default=False)
    terms_accepted: bool = Field(default=False)
    biometric_enabled: bool = Field(default=False)
    segment: Optional[CustomerSegment] = Field(default=None)
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    total_orders: int = Field(default=0)
    total_spent: float = Field(default=0.0)
    last_order_at: Optional[datetime] = Field(default=None)
    is_online: bool = Field(default=False)
    last_seen_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RetailerProfile(SQLModel, table=True):
    __tablename__ = "retailer_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    shop_name: str = Field(max_length=200)
    owner_name: Optional[str] = Field(default=None, max_length=120)
    gstin: Optional[str] = Field(default=None, max_length=20)
    credit_allowed: bool = Field(default=True)
    credit_limit: float = Field(default=50000.0)
    outstanding_balance: float = Field(default=0.0)
    payable_balance: float = Field(default=0.0)
    is_wholesaler: bool = Field(default=True)
    upi_id: Optional[str] = Field(default=None, max_length=100)
    bank_account: Optional[str] = Field(default=None, max_length=40)
    is_blocked: bool = Field(default=False)
    approval_status: str = Field(default="approved", max_length=20, index=True)
    # Seller subscription: none | pending | approved | rejected | expired
    sell_subscription_status: str = Field(default="none", max_length=20, index=True)
    sell_plan: Optional[str] = Field(default=None, max_length=20)  # monthly | yearly
    sell_subscription_expires_at: Optional[datetime] = Field(default=None)
    # payment_link_id:cadence:amount pending Razorpay pay
    sell_rz_pending: Optional[str] = Field(default=None, max_length=255)
    address_line: Optional[str] = Field(default=None, max_length=255)
    village: Optional[str] = Field(default=None, max_length=120)
    area: Optional[str] = Field(default=None, max_length=120)
    city: str = Field(default="Bhubaneswar", max_length=100)
    state: str = Field(default="Odisha", max_length=100)
    zone: Optional[str] = Field(default=None, max_length=80)
    pincode: Optional[str] = Field(default=None, max_length=10)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    aadhaar_number: Optional[str] = Field(default=None, max_length=20)
    aadhaar_url: Optional[str] = Field(default=None, max_length=500)
    pan_number: Optional[str] = Field(default=None, max_length=20)
    pan_url: Optional[str] = Field(default=None, max_length=500)
    shop_logo_url: Optional[str] = Field(default=None, max_length=500)
    shop_open_time: Optional[str] = Field(default="09:00", max_length=10)
    shop_close_time: Optional[str] = Field(default="21:00", max_length=10)
    shop_days: Optional[str] = Field(default="Mon-Sun", max_length=80)
    is_open: bool = Field(default=True)
    # Shop settings (retailer-owned)
    delivery_zones: Optional[str] = Field(default=None, sa_column=Column(Text))
    delivery_charge: float = Field(default=0.0)
    delivery_charge_far: float = Field(default=0.0)
    delivery_radius_km: float = Field(default=3.0)
    min_order_value: float = Field(default=0.0)
    cancellation_policy: Optional[str] = Field(default=None, sa_column=Column(Text))
    return_policy: Optional[str] = Field(default=None, sa_column=Column(Text))
    refund_policy: Optional[str] = Field(default=None, sa_column=Column(Text))
    chatbot_enabled: bool = Field(default=True)
    call_enabled: bool = Field(default=True)
    notifications_enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)
