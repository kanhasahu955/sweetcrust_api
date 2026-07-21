from __future__ import annotations

from datetime import date, time
from typing import Any, Optional

from pydantic import Field

from package.common.schemas import APIModel


class AddressIn(APIModel):
    label: str = "Home"
    full_name: str
    phone: str
    line1: str
    line2: Optional[str] = None
    landmark: Optional[str] = None
    city: str = "Mumbai"
    state: str = "Maharashtra"
    pincode: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_default: bool = False


class CartItemIn(APIModel):
    product_id: int
    quantity: int = Field(1, ge=1)
    variant: Optional[str] = None
    flavor: Optional[str] = None
    is_eggless: bool = False


class CartItemUpdateIn(APIModel):
    quantity: Optional[int] = Field(None, ge=1)
    saved_for_later: Optional[bool] = None


class CouponApplyIn(APIModel):
    code: str


class CheckoutIn(APIModel):
    address_id: int
    delivery_date: date
    delivery_slot: str
    customer_phone: str
    delivery_instructions: Optional[str] = None
    contactless: bool = False
    payment_method: str
    coupon_code: Optional[str] = None


class CustomCakeIn(APIModel):
    occasion: str
    cake_type: str
    flavor: str
    weight: str
    shape: str
    is_eggless: bool = True
    cream_type: Optional[str] = None
    decoration_theme: Optional[str] = None
    reference_image_url: Optional[str] = None
    cake_message: Optional[str] = None
    special_instructions: Optional[str] = None
    delivery_date: Optional[date] = None
    delivery_time: Optional[time] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None


class ReturnIn(APIModel):
    order_id: int
    affected_item_ids: list[int]
    issue_type: str
    solution: str
    description: Optional[str] = None
    evidence_urls: Optional[list[str]] = None


class OrderRateIn(APIModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class ConversationCreateIn(APIModel):
    category: str = "general"
    order_id: Optional[int] = None
    return_id: Optional[int] = None
    custom_cake_id: Optional[int] = None
    is_ai: bool = False
    initial_message: Optional[str] = None


class MessageIn(APIModel):
    content: Optional[str] = None
    message_type: str = "text"
    media_url: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
