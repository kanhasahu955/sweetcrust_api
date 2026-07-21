from typing import Optional

from pydantic import BaseModel, Field


class ProductListQuery(BaseModel):
    category_id: Optional[int] = None
    brand_name: Optional[str] = None
    supplier_user_id: Optional[int] = None
    q: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    flavor: Optional[str] = None
    weight: Optional[str] = None
    eggless: Optional[bool] = None
    sugar_free: Optional[bool] = None
    min_rating: Optional[float] = None
    same_day: Optional[bool] = None
    in_stock: Optional[bool] = None
    offers: Optional[bool] = None
    sort: str = "popular"
    page: int = 1
    page_size: int = 20


class ReviewIn(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    order_id: Optional[int] = None
