"""Thin User — auth deps + favorite/review FKs (auth service owns writes)."""
from datetime import datetime
from typing import Optional

from package.common.utils import utc_now
from sqlmodel import Field, SQLModel

from app.models.enums import UserRole


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    phone: str = Field(index=True, unique=True, max_length=20)
    name: Optional[str] = Field(default=None, max_length=120)
    email: Optional[str] = Field(default=None, max_length=255, index=True)
    password_hash: Optional[str] = Field(default=None, max_length=255)
    role: UserRole = Field(default=UserRole.CUSTOMER, index=True)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    language: str = Field(default="en", max_length=10)
    is_active: bool = Field(default=True)
    is_guest: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RetailerProfile(SQLModel, table=True):
    """Read-only shop profiles for customer marketplace browse."""

    __tablename__ = "retailer_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    shop_name: str = Field(max_length=200)
    owner_name: Optional[str] = Field(default=None, max_length=120)
    is_blocked: bool = Field(default=False)
    approval_status: str = Field(default="approved", max_length=20, index=True)
    address_line: Optional[str] = Field(default=None, max_length=255)
    village: Optional[str] = Field(default=None, max_length=120)
    area: Optional[str] = Field(default=None, max_length=120)
    city: str = Field(default="Bhubaneswar", max_length=100)
    state: str = Field(default="Odisha", max_length=100)
    pincode: Optional[str] = Field(default=None, max_length=10)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    shop_logo_url: Optional[str] = Field(default=None, max_length=500)
    shop_open_time: Optional[str] = Field(default="09:00", max_length=10)
    shop_close_time: Optional[str] = Field(default="21:00", max_length=10)
    shop_days: Optional[str] = Field(default="Mon-Sun", max_length=80)
    is_open: bool = Field(default=True)
    is_wholesaler: bool = Field(default=True)
