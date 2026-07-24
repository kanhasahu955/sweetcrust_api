from enum import Enum


class UserRole(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    DELIVERY = "delivery"
    RETAILER = "retailer"


class StockStatus(str, Enum):
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"


class OrderStatus(str, Enum):
    PLACED = "placed"
    PAYMENT_RECEIVED = "payment_received"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PREPARING = "preparing"
    PACKED = "packed"
    DELIVERY_OFFERED = "delivery_offered"
    DELIVERY_ASSIGNED = "delivery_assigned"
    PICKED_UP = "picked_up"
    OUT_FOR_DELIVERY = "out_for_delivery"
    NEAR_LOCATION = "near_location"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURN_REQUESTED = "return_requested"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, Enum):
    UPI = "upi"
    UPI_QR = "upi_qr"
    GOOGLE_PAY = "google_pay"
    PHONEPE = "phonepe"
    PAYTM = "paytm"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    NET_BANKING = "net_banking"
    WALLET = "wallet"
    COD = "cod"
    CREDIT = "credit"  # shop udhaar / credit ledger
    RAZORPAY = "razorpay"


class ProductFulfillmentType(str, Enum):
    LOCAL_FRESH = "local_fresh"
    SHIPPABLE_PACKAGED = "shippable_packaged"
    BOTH = "both"


class OrderType(str, Enum):
    B2B_SHOP_ORDER = "b2b_shop_order"
    B2C_LOCAL_ORDER = "b2c_local_order"
    B2C_SHIPPING_ORDER = "b2c_shipping_order"


class CreditEntryType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    ADJUSTMENT = "adjustment"


class ChatCategory(str, Enum):
    GENERAL = "general"
    ORDER = "order"
    CUSTOM_CAKE = "custom_cake"
    DELIVERY = "delivery"
    RETURN = "return"
    AI = "ai"
    RETAILER = "retailer"
    RETAILER_AI = "retailer_ai"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    VOICE = "voice"
    PRODUCT = "product"
    LOCATION = "location"
    INVOICE = "invoice"
    PAYMENT_LINK = "payment_link"
    ORDER_CARD = "order_card"
    RETURN_CARD = "return_card"
    SYSTEM = "system"


class ReturnIssueType(str, Enum):
    DAMAGED = "damaged"
    WRONG_PRODUCT = "wrong_product"
    MISSING = "missing"
    STALE = "stale"
    QUALITY = "quality"
    MELTED = "melted"
    PACKAGING = "packaging"
    QUANTITY_MISMATCH = "quantity_mismatch"


class ReturnSolution(str, Enum):
    REFUND = "refund"
    REPLACEMENT = "replacement"


class ReturnStatus(str, Enum):
    SUBMITTED = "submitted"
    AI_VALIDATED = "ai_validated"
    ADMIN_REVIEW = "admin_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REPLACEMENT_INITIATED = "replacement_initiated"
    REFUND_INITIATED = "refund_initiated"
    COMPLETED = "completed"


class CustomCakeStatus(str, Enum):
    REQUESTED = "requested"
    UNDER_REVIEW = "under_review"
    QUOTATION_SENT = "quotation_sent"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CallType(str, Enum):
    PHONE = "phone"
    INTERNET_AUDIO = "internet_audio"
    VIDEO = "video"


class CallStatus(str, Enum):
    RINGING = "ringing"
    ONGOING = "ongoing"
    MISSED = "missed"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class CouponType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    BOGO = "bogo"
    FREE_DELIVERY = "free_delivery"
    PRODUCT = "product"
    CATEGORY = "category"
    FESTIVAL = "festival"
    FIRST_ORDER = "first_order"


class NotificationType(str, Enum):
    ORDER = "order"
    PAYMENT = "payment"
    DELIVERY = "delivery"
    CHAT = "chat"
    CALL = "call"
    RETURN = "return"
    OFFER = "offer"
    PRODUCT = "product"
    AI = "ai"
    CUSTOM_CAKE = "custom_cake"
    STOCK = "stock"
    SYSTEM = "system"


class CustomerSegment(str, Enum):
    NEW = "new"
    LOYAL = "loyal"
    HIGH_VALUE = "high_value"
    INACTIVE = "inactive"
    DISCOUNT_FOCUSED = "discount_focused"
    CAKE = "cake"
    CORPORATE = "corporate"
