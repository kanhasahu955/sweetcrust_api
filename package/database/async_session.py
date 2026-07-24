"""Async SQLAlchemy engine + session (mysql+asyncmy).

Keeps the event loop free for concurrent requests. Sync business code can still
run via ``await session.run_sync(fn)`` during migration.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session as SQLModelSession, SQLModel

from package.common.settings import get_settings

logger = logging.getLogger("package.database.async")

_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def to_async_url(url: str) -> str:
    """mysql+pymysql://… → mysql+asyncmy://…"""
    u = (url or "").strip()
    for old, new in (
        ("mysql+pymysql://", "mysql+asyncmy://"),
        ("mysql+mysqldb://", "mysql+asyncmy://"),
        ("mysql://", "mysql+asyncmy://"),
    ):
        if u.startswith(old):
            return new + u[len(old) :]
    return u


def get_async_engine() -> AsyncEngine:
    global _async_engine, _async_session_factory
    if _async_engine is None:
        s = get_settings()
        _async_engine = create_async_engine(
            to_async_url(s.database_url),
            echo=s.db_echo,
            pool_pre_ping=True,
            pool_recycle=s.db_pool_recycle,
            pool_size=s.db_pool_size,
            max_overflow=s.db_max_overflow,
            pool_timeout=s.db_pool_timeout,
        )
        _async_session_factory = async_sessionmaker(
            _async_engine,
            class_=AsyncSession,
            sync_session_class=SQLModelSession,  # run_sync → .exec() for sync SQLModel code
            expire_on_commit=False,
        )
        logger.info("async engine ready (asyncmy)")
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    get_async_engine()
    assert _async_session_factory is not None
    return _async_session_factory


async def connect_async_db() -> AsyncEngine:
    return get_async_engine()


async def disconnect_async_db() -> None:
    global _async_engine, _async_session_factory
    if _async_engine is not None:
        await _async_engine.dispose()
        logger.info("async engine disconnected")
    _async_engine = None
    _async_session_factory = None


async def ping_async_db() -> bool:
    from sqlalchemy import text

    try:
        eng = get_async_engine()
        async with eng.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("async db ping failed: %s", exc.__class__.__name__)
        return False


def _migrate_columns_sync(conn) -> None:
    """Best-effort ADD COLUMN for existing MySQL DBs (ignore if already present)."""
    from sqlalchemy import text as sa_text

    alters = [
        "ALTER TABLE products ADD COLUMN brand_name VARCHAR(120) NULL",
        "ALTER TABLE products ADD COLUMN supplier_user_id INT NULL",
        "ALTER TABLE products ADD COLUMN supplier_available_qty INT NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN shop_user_id INT NULL",
        "ALTER TABLE orders ADD COLUMN paid_amount DOUBLE NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN offer_expires_at DATETIME NULL",
        "CREATE INDEX ix_products_brand_name ON products (brand_name)",
        "CREATE INDEX ix_products_supplier_user_id ON products (supplier_user_id)",
        "CREATE INDEX ix_orders_shop_user_id ON orders (shop_user_id)",
        # users — create_all does not add columns to existing tables
        "ALTER TABLE users ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN terms_accepted TINYINT(1) NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN biometric_enabled TINYINT(1) NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN segment VARCHAR(40) NULL",
        "ALTER TABLE users ADD COLUMN notes TEXT NULL",
        "ALTER TABLE users ADD COLUMN total_orders INT NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN total_spent DOUBLE NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN last_order_at DATETIME NULL",
        "ALTER TABLE users ADD COLUMN is_online TINYINT(1) NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN last_seen_at DATETIME NULL",
        # retailer seller mode
        "ALTER TABLE categories ADD COLUMN parent_id INT NULL",
        "ALTER TABLE categories ADD COLUMN owner_user_id INT NULL",
        "ALTER TABLE retailer_profiles ADD COLUMN sell_subscription_status VARCHAR(20) NOT NULL DEFAULT 'none'",
        "ALTER TABLE retailer_profiles ADD COLUMN sell_plan VARCHAR(20) NULL",
        "ALTER TABLE retailer_profiles ADD COLUMN sell_subscription_expires_at DATETIME NULL",
        "ALTER TABLE retailer_profiles ADD COLUMN sell_rz_pending VARCHAR(255) NULL",
        "ALTER TABLE retailer_profiles ADD COLUMN delivery_zones TEXT NULL",
        "ALTER TABLE retailer_profiles ADD COLUMN delivery_charge DOUBLE NOT NULL DEFAULT 0",
        "ALTER TABLE retailer_profiles ADD COLUMN delivery_charge_far DOUBLE NOT NULL DEFAULT 0",
        "ALTER TABLE retailer_profiles ADD COLUMN delivery_radius_km DOUBLE NOT NULL DEFAULT 3",
        "ALTER TABLE retailer_profiles ADD COLUMN min_order_value DOUBLE NOT NULL DEFAULT 0",
        "ALTER TABLE retailer_profiles ADD COLUMN cancellation_policy TEXT NULL",
        "ALTER TABLE retailer_profiles ADD COLUMN return_policy TEXT NULL",
        "ALTER TABLE retailer_profiles ADD COLUMN refund_policy TEXT NULL",
        "ALTER TABLE retailer_profiles ADD COLUMN chatbot_enabled TINYINT(1) NOT NULL DEFAULT 1",
        "ALTER TABLE retailer_profiles ADD COLUMN call_enabled TINYINT(1) NOT NULL DEFAULT 1",
        "ALTER TABLE retailer_profiles ADD COLUMN notifications_enabled TINYINT(1) NOT NULL DEFAULT 1",
        "ALTER TABLE banners ADD COLUMN shop_user_id INT NULL",
        "ALTER TABLE coupons ADD COLUMN shop_user_id INT NULL",
        "CREATE INDEX ix_categories_parent_id ON categories (parent_id)",
        "CREATE INDEX ix_categories_owner_user_id ON categories (owner_user_id)",
        "CREATE INDEX ix_banners_shop_user_id ON banners (shop_user_id)",
        "CREATE INDEX ix_coupons_shop_user_id ON coupons (shop_user_id)",
        "ALTER TABLE invoices MODIFY COLUMN order_id INT NULL",
        "ALTER TABLE invoices ADD COLUMN kind VARCHAR(40) NOT NULL DEFAULT 'customer_order'",
        "ALTER TABLE invoices ADD COLUMN ref_type VARCHAR(40) NULL",
        "ALTER TABLE invoices ADD COLUMN ref_id VARCHAR(80) NULL",
        "ALTER TABLE invoices ADD COLUMN buyer_user_id INT NULL",
        "ALTER TABLE invoices ADD COLUMN seller_user_id INT NULL",
        "CREATE INDEX ix_invoices_kind ON invoices (kind)",
        "CREATE INDEX ix_invoices_ref_type ON invoices (ref_type)",
        "CREATE INDEX ix_invoices_ref_id ON invoices (ref_id)",
        "CREATE INDEX ix_invoices_buyer_user_id ON invoices (buyer_user_id)",
        "CREATE INDEX ix_invoices_seller_user_id ON invoices (seller_user_id)",
    ]
    for sql in alters:
        try:
            conn.execute(sa_text(sql))
        except Exception:
            pass


async def init_async_db() -> None:
    eng = get_async_engine()
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.run_sync(_migrate_columns_sync)
    logger.info("init_async_db create_all done")


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
        except SQLAlchemyError:
            await session.rollback()
            raise


AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]
