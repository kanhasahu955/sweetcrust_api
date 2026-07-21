"""Catalog tables AI reads for RAG / tools / insights."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel

from app.models.enums import StockStatus


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=120)
    slug: str = Field(unique=True, index=True, max_length=140)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    image_url: Optional[str] = Field(default=None, max_length=500)
    display_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="categories.id", index=True)
    # Wholesaler shop brand you buy from (same item type = separate SKU per brand)
    brand_name: Optional[str] = Field(default=None, index=True, max_length=120)
    supplier_user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    name: str = Field(index=True, max_length=200)
    slug: str = Field(unique=True, index=True, max_length=220)
    short_description: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    ingredients: Optional[str] = Field(default=None, sa_column=Column(Text))
    allergens: Optional[str] = Field(default=None, max_length=500)
    nutrition_info: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    flavor: Optional[str] = Field(default=None, max_length=100)
    weight: Optional[str] = Field(default=None, max_length=50)
    unit_label: str = Field(default="pcs", max_length=40)
    selling_price: float = Field(default=0.0)
    customer_price: Optional[float] = Field(default=None)
    shop_price: Optional[float] = Field(default=None)
    purchase_cost: Optional[float] = Field(default=None)
    fulfillment_type: str = Field(default="both", max_length=40)
    min_order_qty: int = Field(default=1)
    original_price: Optional[float] = Field(default=None)
    discount_percent: float = Field(default=0.0)
    gst_rate: float = Field(default=5.0)
    stock_qty: int = Field(default=0)
    stock_status: StockStatus = Field(default=StockStatus.IN_STOCK, index=True)
    low_stock_threshold: int = Field(default=5)
    rating: float = Field(default=0.0)
    review_count: int = Field(default=0)
    sales_count: int = Field(default=0)
    is_eggless: bool = Field(default=False)
    is_sugar_free: bool = Field(default=False)
    is_vegan: bool = Field(default=False)
    is_freshly_baked: bool = Field(default=True)
    same_day_delivery: bool = Field(default=True)
    preparation_minutes: int = Field(default=60)
    shelf_life_hours: Optional[int] = Field(default=24)
    storage_instructions: Optional[str] = Field(default=None, max_length=500)
    estimated_delivery_mins: int = Field(default=45)
    return_eligible: bool = Field(default=True)
    cover_image_url: Optional[str] = Field(default=None, max_length=500)
    video_url: Optional[str] = Field(default=None, max_length=500)
    tags: Optional[list] = Field(default=None, sa_column=Column(JSON))
    filters: Optional[list] = Field(default=None, sa_column=Column(JSON))
    available_sizes: Optional[list] = Field(default=None, sa_column=Column(JSON))
    available_flavors: Optional[list] = Field(default=None, sa_column=Column(JSON))
    quality_score: Optional[float] = Field(default=None)
    quality_suggestions: Optional[list] = Field(default=None, sa_column=Column(JSON))
    is_active: bool = Field(default=True)
    is_draft: bool = Field(default=False)
    is_trending: bool = Field(default=False)
    is_bestseller: bool = Field(default=False)
    is_festival: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
