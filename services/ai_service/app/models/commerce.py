"""Order tables AI reads for status / tools (owned by commerce service long-term)."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel

from app.models.enums import OrderStatus, PaymentMethod, PaymentStatus


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_number: str = Field(unique=True, index=True, max_length=40)
    user_id: int = Field(foreign_key="users.id", index=True)
    shop_user_id: Optional[int] = Field(default=None, index=True)
    order_type: str = Field(default="b2c_local_order", index=True, max_length=40)
    # Cross-service ids — no FK so AI metadata stays lean
    address_id: Optional[int] = Field(default=None, index=True)
    delivery_person_id: Optional[int] = Field(default=None, index=True)
    status: OrderStatus = Field(default=OrderStatus.PLACED, index=True)
    payment_status: PaymentStatus = Field(default=PaymentStatus.PENDING, index=True)
    payment_method: Optional[PaymentMethod] = Field(default=None)
    subtotal: float = Field(default=0.0)
    discount: float = Field(default=0.0)
    coupon_code: Optional[str] = Field(default=None, max_length=50)
    gst_amount: float = Field(default=0.0)
    delivery_fee: float = Field(default=0.0)
    final_amount: float = Field(default=0.0)
    delivery_date: Optional[date] = Field(default=None)
    delivery_slot: Optional[str] = Field(default=None, max_length=50)
    delivery_instructions: Optional[str] = Field(default=None, sa_column=Column(Text))
    contactless: bool = Field(default=False)
    customer_phone: Optional[str] = Field(default=None, max_length=20)
    address_snapshot: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    estimated_delivery_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    cancelled_at: Optional[datetime] = Field(default=None)
    cancel_reason: Optional[str] = Field(default=None, max_length=500)
    internal_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    rating: Optional[int] = Field(default=None)
    rating_comment: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    product_name: str = Field(max_length=200)
    product_image: Optional[str] = Field(default=None, max_length=500)
    variant: Optional[str] = Field(default=None, max_length=120)
    flavor: Optional[str] = Field(default=None, max_length=100)
    is_eggless: bool = Field(default=False)
    quantity: int = Field(default=1)
    unit_price: float = Field(default=0.0)
    total_price: float = Field(default=0.0)
    unit_cost: float = Field(default=0.0)
