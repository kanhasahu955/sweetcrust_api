"""Database engine, sessions, lifespan, pool metrics, optional read replica."""
from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Annotated, Optional

from fastapi import Depends
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine

from package.common.settings import get_settings

logger = logging.getLogger("package.database")

_engine: Engine | None = None
_read_engine: Engine | None = None


def _build_engine(url: str, *, echo: bool) -> Engine:
    s = get_settings()
    eng = create_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_recycle=s.db_pool_recycle,
        pool_size=s.db_pool_size,
        max_overflow=s.db_max_overflow,
        pool_timeout=s.db_pool_timeout,
    )
    if s.db_log_slow_ms > 0:
        _attach_slow_query_logger(eng, s.db_log_slow_ms)
    return eng


def _attach_slow_query_logger(eng: Engine, threshold_ms: int) -> None:
    @event.listens_for(eng, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
        conn.info["query_start"] = time.perf_counter()

    @event.listens_for(eng, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
        start = conn.info.pop("query_start", None)
        if start is None:
            return
        ms = (time.perf_counter() - start) * 1000
        if ms >= threshold_ms:
            logger.warning("slow query %.1fms :: %s", ms, (statement or "")[:200])


def get_engine(*, readonly: bool = False) -> Engine:
    """Primary engine, or read-replica / LB VIP when `database_read_url` is set."""
    global _engine, _read_engine
    s = get_settings()
    if readonly and s.database_read_url:
        if _read_engine is None:
            _read_engine = _build_engine(s.database_read_url, echo=s.db_echo)
            logger.info("read engine ready (replica / LB)")
        return _read_engine
    if _engine is None:
        _engine = _build_engine(s.database_url, echo=s.db_echo)
        logger.info("write engine ready")
    return _engine


class _EngineProxy:
    def __getattr__(self, name: str):
        return getattr(get_engine(), name)

    def begin(self, *a, **kw):
        return get_engine().begin(*a, **kw)

    def connect(self, *a, **kw):
        return get_engine().connect(*a, **kw)


engine = _EngineProxy()  # type: ignore[assignment]


def connect_db() -> Engine:
    """Eagerly create primary (and optional read) engines."""
    eng = get_engine()
    s = get_settings()
    if s.database_read_url:
        get_engine(readonly=True)
    return eng


def disconnect_db() -> None:
    """Dispose pools — call on lifespan shutdown."""
    global _engine, _read_engine
    for label, eng in (("write", _engine), ("read", _read_engine)):
        if eng is not None:
            eng.dispose()
            logger.info("%s engine disconnected", label)
    _engine = None
    _read_engine = None


def reset_engine() -> None:
    disconnect_db()


def ping_db(*, readonly: bool = False) -> bool:
    try:
        with get_engine(readonly=readonly).connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("db ping failed: %s", exc.__class__.__name__)
        return False


def pool_status() -> dict:
    eng = get_engine()
    pool = eng.pool
    return {
        "pool_size": getattr(pool, "size", lambda: None)(),
        "checked_in": getattr(pool, "checkedin", lambda: None)(),
        "checked_out": getattr(pool, "checkedout", lambda: None)(),
        "overflow": getattr(pool, "overflow", lambda: None)(),
        "has_read_replica": bool(get_settings().database_read_url),
    }


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        try:
            yield session
        except SQLAlchemyError:
            session.rollback()
            raise


def get_read_session() -> Generator[Session, None, None]:
    """Prefer read replica / LB VIP when configured; else primary."""
    with Session(get_engine(readonly=True)) as session:
        try:
            yield session
        except SQLAlchemyError:
            session.rollback()
            raise


@contextmanager
def session_scope(*, readonly: bool = False) -> Generator[Session, None, None]:
    """Non-FastAPI context manager for scripts / workers."""
    with Session(get_engine(readonly=readonly)) as session:
        try:
            yield session
            if not readonly:
                session.commit()
        except Exception:
            session.rollback()
            raise


SessionDep = Annotated[Session, Depends(get_session)]
ReadSessionDep = Annotated[Session, Depends(get_read_session)]


def _migrate_columns(engine: Engine) -> None:
    """Best-effort ADD COLUMN for existing MySQL DBs (ignore if already present)."""
    alters = [
        "ALTER TABLE products ADD COLUMN brand_name VARCHAR(120) NULL",
        "ALTER TABLE products ADD COLUMN supplier_user_id INT NULL",
        "ALTER TABLE products ADD COLUMN supplier_available_qty INT NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN shop_user_id INT NULL",
        "ALTER TABLE orders ADD COLUMN paid_amount DOUBLE NOT NULL DEFAULT 0",
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
    ]
    with engine.begin() as conn:
        for sql in alters:
            try:
                conn.execute(text(sql))
            except Exception:
                pass


def init_db() -> None:
    """Create tables for models the service has already imported."""
    eng = get_engine()
    SQLModel.metadata.create_all(eng)
    _migrate_columns(eng)
    logger.info("init_db create_all done")
