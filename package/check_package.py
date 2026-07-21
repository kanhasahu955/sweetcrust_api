"""ponytail: package surface sanity — run: PYTHONPATH=backend_v2 python -m package.check_package"""
from __future__ import annotations


def main() -> None:
    from package.common.auth import load_user, load_user_async, make_async_user_deps, make_user_deps
    from package.common.base import BaseController, BaseRepository, BaseService
    from package.common.errors import AppError, ConflictError, NotFoundError, RateLimitError
    from package.common.factory import create_service_app
    from package.common.lifecycle import service_lifespan
    from package.common.middleware import setup_middleware
    from package.common.rate_limit import enforce_rate
    from package.common.routing import register_routes
    from package.common.schemas import APIModel, ErrorBody, HealthOut, fail, ok
    from package.common.env import ROOT_ENV
    from package.common.settings import Settings, get_settings, reload_settings
    from package.common.utils import day_bounds, utc_now, utc_now_aware, utc_today
    from package.database import (
        AsyncSessionDep,
        connect_db,
        disconnect_db,
        ping_db,
        pool_status,
        session_scope,
        to_async_url,
    )
    from package.dto import MessageOut
    from package.events.topics import ADMIN_EVENT, CHAT_MESSAGE, DELIVERY_LOCATION, ORDER_STATUS, USER_EVENT
    from package.logger import get_logger, log_service_boot, setup_logging
    from package.redis import redis_publish

    setup_logging("INFO", color=False)
    log = get_logger("check")
    assert ROOT_ENV.is_file(), f"missing credentials file: {ROOT_ENV}"
    s = reload_settings()
    assert isinstance(s, Settings)
    assert "service_name" in s.public_dict()
    assert s.jwt_secret_key and s.jwt_secret_key != "change-me", "JWT not loaded from backend_v2/.env"
    assert "sweetcrust" in s.database_url, "DATABASE_URL not loaded from backend_v2/.env"

    body = ok({"a": 1}, message="hi")
    assert body["success"] is True
    err = fail("nope", code="x")
    assert err["success"] is False and err["code"] == "x"

    e = NotFoundError("missing")
    assert e.status_code == 404
    assert issubclass(ConflictError, AppError)

    now = utc_now()
    assert now.tzinfo is None
    assert utc_now_aware().tzinfo is not None
    assert utc_today() == now.date()
    start, end = day_bounds()
    assert start < end
    assert CHAT_MESSAGE and ORDER_STATUS and DELIVERY_LOCATION and ADMIN_EVENT and USER_EVENT

    # boot helpers importable (no live DB required for this check)
    assert callable(connect_db)
    assert callable(disconnect_db)
    assert callable(ping_db)
    assert callable(pool_status)
    assert callable(session_scope)
    assert callable(setup_middleware)
    assert callable(service_lifespan)
    assert callable(create_service_app)
    assert callable(log_service_boot)
    assert callable(enforce_rate)
    assert callable(load_user)
    assert callable(load_user_async)
    assert callable(make_user_deps)
    assert callable(make_async_user_deps)
    assert callable(register_routes)
    assert callable(to_async_url)
    assert "asyncmy" in to_async_url("mysql+pymysql://u@h/db")
    assert issubclass(BaseRepository, object)
    assert issubclass(BaseService, object)
    assert issubclass(BaseController, object)
    assert AsyncSessionDep is not None
    assert callable(redis_publish)
    assert issubclass(APIModel, object)
    assert issubclass(RateLimitError, AppError)
    assert ErrorBody(detail="x").success is False
    assert HealthOut(service="x", ok=True).ok is True
    assert MessageOut(message="ok").success is True

    log.info("package check ok · settings/logger/database/async/oop/factory ready")
    print("package check ok")


if __name__ == "__main__":
    main()
