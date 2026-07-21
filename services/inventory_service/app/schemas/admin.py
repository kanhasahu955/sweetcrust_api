from __future__ import annotations

from typing import Optional

from package.common.schemas import APIModel


class ProductIn(APIModel):
    category_id: int
    name: str
    short_description: Optional[str] = None
    description: Optional[str] = None
    ingredients: Optional[str] = None
    allergens: Optional[str] = None
    flavor: Optional[str] = None
    weight: Optional[str] = None
    selling_price: float = 0
    customer_price: Optional[float] = None
    shop_price: Optional[float] = None
    original_price: Optional[float] = None
    gst_rate: float = 5.0
    stock_qty: int = 0
    is_eggless: bool = False
    is_sugar_free: bool = False
    preparation_minutes: int = 60
    shelf_life_hours: Optional[int] = None
    storage_instructions: Optional[str] = None
    tags: Optional[list] = None
    filters: Optional[list] = None
    cover_image_url: Optional[str] = None
    is_draft: bool = False
    is_active: bool = True


class ProductPatchIn(APIModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    selling_price: Optional[float] = None
    stock_qty: Optional[int] = None
    is_active: Optional[bool] = None
    is_draft: Optional[bool] = None
    cover_image_url: Optional[str] = None
    tags: Optional[list] = None
    shop_price: Optional[float] = None
    customer_price: Optional[float] = None


class StockUpdateIn(APIModel):
    stock_qty: int
    reason: str = "adjust"
    note: Optional[str] = None


class CategoryIn(APIModel):
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    display_order: int = 0
    is_active: bool = True


class CouponIn(APIModel):
    code: str
    title: str
    description: Optional[str] = None
    coupon_type: str = "percentage"
    value: float = 0
    min_order_amount: float = 0
    max_discount: Optional[float] = None
    is_active: bool = True


class OrderStatusUpdateIn(APIModel):
    status: str
    note: Optional[str] = None
    delivery_person_id: Optional[int] = None


class DeliveryAssignIn(APIModel):
    delivery_person_id: int


class DeliveryPersonIn(APIModel):
    name: str
    phone: str
    vehicle_number: str
    default_trip_cost: float = 40.0
    is_available: bool = True


class DeliveryPersonPatchIn(APIModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    vehicle_number: Optional[str] = None
    is_available: Optional[bool] = None
    default_trip_cost: Optional[float] = None


class SettingsUpdateIn(APIModel):
    bakery_name: Optional[str] = None
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    upi_id: Optional[str] = None
    delivery_charge: Optional[float] = None
    free_delivery_min: Optional[float] = None
    min_order_value: Optional[float] = None
    cod_enabled: Optional[bool] = None


class ShopCreateIn(APIModel):
    phone: str
    password: str
    shop_name: str
    owner_name: str
    village: Optional[str] = None
    area: Optional[str] = None
    zone: Optional[str] = None
    city: str = "Bhubaneswar"
    state: str = "Odisha"
    pincode: Optional[str] = None
    address_line: Optional[str] = None
    gstin: Optional[str] = None
    contact_phone: Optional[str] = None
    credit_allowed: bool = True
    credit_limit: float = 50000


class ShopPatchIn(APIModel):
    is_blocked: Optional[bool] = None
    credit_allowed: Optional[bool] = None
    credit_limit: Optional[float] = None
    contact_phone: Optional[str] = None
    zone: Optional[str] = None
    village: Optional[str] = None
    is_wholesaler: Optional[bool] = None
    upi_id: Optional[str] = None
    bank_account: Optional[str] = None


class BannerIn(APIModel):
    title: str
    subtitle: Optional[str] = None
    image_url: str
    link_type: Optional[str] = None
    link_value: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class MessageIn(APIModel):
    content: Optional[str] = None
    message_type: str = "text"
    media_url: Optional[str] = None
    metadata_json: Optional[dict] = None


class ReturnAdminIn(APIModel):
    status: str
    admin_response: Optional[str] = None
    internal_note: Optional[str] = None
    refund_amount: Optional[float] = None


class RetailerProfilePatchIn(APIModel):
    shop_name: Optional[str] = None
    owner_name: Optional[str] = None
    village: Optional[str] = None
    area: Optional[str] = None
    is_open: Optional[bool] = None


class SupplierPurchaseIn(APIModel):
    supplier_user_id: int
    product_id: int
    qty: int
    unit_cost: float
    note: Optional[str] = None
    mark_paid: bool = False
    pay_method: Optional[str] = "upi"


class SupplierPayIn(APIModel):
    amount: Optional[float] = None
    pay_method: str = "upi"
    note: Optional[str] = None


class CustomCakeAdminIn(APIModel):
    status: str
    quoted_price: Optional[float] = None


class CollectIn(APIModel):
    amount: float
    note: Optional[str] = None
    method: str = "upi"


class ProductRequestIn(APIModel):
    image_urls: list[str]
    cover_image: Optional[str] = None
    suggestions: dict
    notes: Optional[str] = None


class BulkLineIn(APIModel):
    product_id: int
    qty: int = 1


class BulkOrderIn(APIModel):
    lines: list[BulkLineIn]
    note: Optional[str] = None
    pay_mode: str = "credit"


class CallbackIn(APIModel):
    note: Optional[str] = None
