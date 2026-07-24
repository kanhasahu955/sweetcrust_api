"""Order tables AI reads for status / tools (owned by commerce service long-term)."""
from datetime import date, datetime, time
from typing import Optional

from package.common.utils import utc_now

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel

from app.models.enums import CustomCakeStatus, OrderStatus, PaymentMethod, PaymentStatus


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
    paid_amount: float = Field(default=0.0)
    delivery_date: Optional[date] = Field(default=None)
    delivery_slot: Optional[str] = Field(default=None, max_length=50)
    delivery_instructions: Optional[str] = Field(default=None, sa_column=Column(Text))
    contactless: bool = Field(default=False)
    customer_phone: Optional[str] = Field(default=None, max_length=20)
    address_snapshot: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    estimated_delivery_at: Optional[datetime] = Field(default=None)
    offer_expires_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    cancelled_at: Optional[datetime] = Field(default=None)
    cancel_reason: Optional[str] = Field(default=None, max_length=500)
    internal_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    rating: Optional[int] = Field(default=None)
    rating_comment: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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


class OrderStatusHistory(SQLModel, table=True):
    __tablename__ = "order_status_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    status: OrderStatus
    note: Optional[str] = Field(default=None, max_length=500)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=utc_now)


class Coupon(SQLModel, table=True):
    __tablename__ = "coupons"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True, max_length=50)
    title: str = Field(max_length=200)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    coupon_type: str = Field(default="percentage", max_length=40)
    value: float = Field(default=0.0)
    min_order_amount: float = Field(default=0.0)
    max_discount: Optional[float] = Field(default=None)
    product_ids: Optional[list] = Field(default=None, sa_column=Column(JSON))
    category_ids: Optional[list] = Field(default=None, sa_column=Column(JSON))
    starts_at: Optional[datetime] = Field(default=None)
    ends_at: Optional[datetime] = Field(default=None)
    usage_limit: Optional[int] = Field(default=None)
    used_count: int = Field(default=0)
    is_active: bool = Field(default=True)
    # null = platform coupon; set for retailer shop offers
    shop_user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)


class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    amount: float
    method: Optional[PaymentMethod] = Field(default=None)
    status: PaymentStatus = Field(default=PaymentStatus.PENDING, index=True)
    transaction_id: Optional[str] = Field(default=None, max_length=100)
    upi_id: Optional[str] = Field(default=None, max_length=100)
    gateway_response: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    failure_reason: Optional[str] = Field(default=None, max_length=500)
    paid_at: Optional[datetime] = Field(default=None)
    refund_amount: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ReturnRequest(SQLModel, table=True):
    __tablename__ = "return_requests"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    issue_type: str = Field(max_length=40)
    solution: str = Field(default="refund", max_length=40)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    evidence_urls: Optional[list] = Field(default=None, sa_column=Column(JSON))
    refund_amount: float = Field(default=0.0)
    status: str = Field(default="submitted", max_length=40, index=True)
    ai_assessment: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    admin_response: Optional[str] = Field(default=None, sa_column=Column(Text))
    internal_note: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"

    id: Optional[int] = Field(default=None, primary_key=True)
    # Nullable so subscription / PO settlements can invoice without a commerce order.
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id", unique=True, index=True)
    # subscription_pack | b2b_wholesale | customer_order | supplier_settlement
    kind: str = Field(default="customer_order", max_length=40, index=True)
    ref_type: Optional[str] = Field(default=None, max_length=40, index=True)
    ref_id: Optional[str] = Field(default=None, max_length=80, index=True)
    buyer_user_id: Optional[int] = Field(default=None, index=True)
    seller_user_id: Optional[int] = Field(default=None, index=True)
    invoice_number: str = Field(unique=True, index=True, max_length=40)
    bakery_name: str = Field(max_length=200)
    gstin: str = Field(max_length=20)
    customer_name: str = Field(max_length=120)
    customer_phone: str = Field(max_length=20)
    customer_address: Optional[str] = Field(default=None, sa_column=Column(Text))
    line_items: dict = Field(default_factory=dict, sa_column=Column(JSON))
    subtotal: float = Field(default=0.0)
    discount: float = Field(default=0.0)
    gst_amount: float = Field(default=0.0)
    delivery_fee: float = Field(default=0.0)
    grand_total: float = Field(default=0.0)
    payment_method: Optional[str] = Field(default=None, max_length=50)
    transaction_id: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    pdf_url: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)


class CustomCakeRequest(SQLModel, table=True):
    __tablename__ = "custom_cake_requests"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    occasion: str = Field(max_length=100)
    cake_type: str = Field(max_length=100)
    flavor: str = Field(max_length=100)
    weight: str = Field(max_length=50)
    shape: str = Field(max_length=50)
    is_eggless: bool = Field(default=True)
    cream_type: Optional[str] = Field(default=None, max_length=100)
    decoration_theme: Optional[str] = Field(default=None, max_length=120)
    reference_image_url: Optional[str] = Field(default=None, max_length=500)
    cake_message: Optional[str] = Field(default=None, max_length=200)
    special_instructions: Optional[str] = Field(default=None, sa_column=Column(Text))
    delivery_date: Optional[date] = Field(default=None)
    delivery_time: Optional[time] = Field(default=None)
    budget_min: Optional[float] = Field(default=None)
    budget_max: Optional[float] = Field(default=None)
    estimated_price: Optional[float] = Field(default=None)
    quoted_price: Optional[float] = Field(default=None)
    ai_suggestions: Optional[list] = Field(default=None, sa_column=Column(JSON))
    status: CustomCakeStatus = Field(default=CustomCakeStatus.REQUESTED, index=True)
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
