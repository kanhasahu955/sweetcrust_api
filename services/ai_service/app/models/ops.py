"""Chat, calls, FAQs, notifications — primary AI write models."""
from datetime import datetime, time
from typing import Optional

from sqlalchemy import Column, JSON, String, Text
from sqlmodel import Field, SQLModel

from app.models.enums import CallStatus, CallType, ChatCategory, MessageType, NotificationType


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: Optional[int] = Field(default=None, primary_key=True)
    category: ChatCategory = Field(
        default=ChatCategory.GENERAL,
        sa_column=Column(String(40), nullable=False, index=True, server_default="general"),
    )
    customer_id: int = Field(foreign_key="users.id", index=True)
    admin_id: Optional[int] = Field(default=None, foreign_key="users.id")
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id")
    # Cross-service refs (return / custom cake live elsewhere)
    return_id: Optional[int] = Field(default=None, index=True)
    custom_cake_id: Optional[int] = Field(default=None, index=True)
    is_ai: bool = Field(default=False)
    ai_handed_over: bool = Field(default=False)
    last_message: Optional[str] = Field(default=None, max_length=500)
    unread_customer: int = Field(default=0)
    unread_admin: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversations.id", index=True)
    sender_id: Optional[int] = Field(default=None, foreign_key="users.id")
    sender_role: str = Field(max_length=20)
    message_type: MessageType = Field(
        default=MessageType.TEXT,
        sa_column=Column(String(40), nullable=False, server_default="text"),
    )
    content: Optional[str] = Field(default=None, sa_column=Column(Text))
    media_url: Optional[str] = Field(default=None, max_length=500)
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    is_delivered: bool = Field(default=False)
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CallRecord(SQLModel, table=True):
    __tablename__ = "call_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    caller_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    callee_id: Optional[int] = Field(default=None, foreign_key="users.id")
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id")
    call_type: CallType = Field(default=CallType.PHONE)
    status: CallStatus = Field(default=CallStatus.RINGING)
    direction: str = Field(default="inbound", max_length=40)
    provider: Optional[str] = Field(default=None, max_length=40)
    provider_call_sid: Optional[str] = Field(default=None, max_length=80, index=True)
    to_phone: Optional[str] = Field(default=None, max_length=20)
    purpose: Optional[str] = Field(default=None, max_length=120)
    transcript: Optional[list] = Field(default=None, sa_column=Column(JSON))
    masked_number: Optional[str] = Field(default=None, max_length=20)
    duration_seconds: int = Field(default=0)
    notes: Optional[str] = Field(default=None, max_length=500)
    started_at: Optional[datetime] = Field(default=None)
    ended_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    type: NotificationType = Field(default=NotificationType.SYSTEM, index=True)
    title: str = Field(max_length=200)
    body: str = Field(sa_column=Column(Text))
    data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BakerySettings(SQLModel, table=True):
    __tablename__ = "bakery_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    bakery_name: str = Field(default="SweetCrust Bakery", max_length=200)
    owner_name: str = Field(default="Priya Sharma", max_length=120)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    address: str = Field(default="12 MG Road, Andheri West, Mumbai 400058", max_length=500)
    latitude: float = Field(default=19.1197)
    longitude: float = Field(default=72.8468)
    phone: str = Field(default="+919876543210", max_length=20)
    email: str = Field(default="hello@sweetcrust.in", max_length=255)
    gstin: str = Field(default="27AABCS1234A1Z5", max_length=20)
    upi_id: str = Field(default="sweetcrust@upi", max_length=100)
    bank_details: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    working_hours: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    delivery_zones: Optional[list] = Field(default=None, sa_column=Column(JSON))
    delivery_charge: float = Field(default=40.0)
    free_delivery_min: float = Field(default=499.0)
    min_order_value: float = Field(default=149.0)
    cod_enabled: bool = Field(default=True)
    tax_settings: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    cancellation_policy: Optional[str] = Field(default=None, sa_column=Column(Text))
    return_policy: Optional[str] = Field(default=None, sa_column=Column(Text))
    refund_policy: Optional[str] = Field(default=None, sa_column=Column(Text))
    chatbot_tone: str = Field(default="warm", max_length=50)
    chatbot_languages: Optional[list] = Field(default=None, sa_column=Column(JSON))
    open_time: Optional[time] = Field(default=None)
    close_time: Optional[time] = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatbotFAQ(SQLModel, table=True):
    __tablename__ = "chatbot_faqs"

    id: Optional[int] = Field(default=None, primary_key=True)
    question: str = Field(sa_column=Column(Text))
    answer: str = Field(sa_column=Column(Text))
    language: str = Field(default="en", max_length=10)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
