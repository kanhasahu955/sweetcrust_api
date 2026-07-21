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
