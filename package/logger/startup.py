"""Pretty boot report: config, DB, Redis, routes, running status."""
from __future__ import annotations

import os
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import FastAPI

from package.logger.setup import get_logger

log = get_logger("package.boot")

_SECRET_KEYS = ("password", "secret", "token", "api_key", "auth", "_pass", "passwd", "private")


def _mask_url(url: str) -> str:
    try:
        p = urlparse(url)
        netloc = p.hostname or ""
        if p.port:
            netloc = f"{netloc}:{p.port}"
        if p.username:
            netloc = f"***@{netloc}"
        return f"{p.scheme}://{netloc}{p.path}"
    except Exception:
        return "***"


def _safe_config(settings: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    data = settings.model_dump() if hasattr(settings, "model_dump") else {}
    for k, v in data.items():
        lk = k.lower()
        if v is None:
            out[k] = None
        elif any(s in lk for s in _SECRET_KEYS):
            out[k] = "***" if v else None
        elif "url" in lk and isinstance(v, str) and "://" in v:
            out[k] = _mask_url(v)
        else:
            out[k] = v
    return out


def _route_lines(app: FastAPI) -> list[str]:
    lines: list[str] = []
    for r in app.routes:
        methods = sorted(getattr(r, "methods", None) or [])
        path = getattr(r, "path", None)
        if not path or not methods:
            continue
        # skip docs noise in summary unless useful
        if path in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"):
            continue
        lines.append(f"{','.join(methods):<12} {path}")
    return sorted(lines)


def log_service_boot(
    app: FastAPI,
    *,
    service: str,
    version: str = "0.1.0",
    db_ok: bool = False,
    redis_ok: Optional[bool] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Call once after routes are mounted and DB connected."""
    from package.common.settings import get_settings
    from package.database import pool_status

    s = get_settings()
    cfg = _safe_config(s)
    routes = _route_lines(app)
    status = "RUNNING" if db_ok else "DEGRADED"
    bar = "═" * 52

    log.info(bar)
    log.info("  %s  v%s  ·  %s", service.upper(), version, status)
    log.info("  env=%s  host=%s  port=%s  pid=%s", s.env, s.host, s.port, os.getpid())
    log.info(bar)

    log.info("— configuration —")
    for k in sorted(cfg):
        log.info("  %-28s %s", k, cfg[k])

    log.info("— connectivity —")
    log.info("  database                     %s", "OK" if db_ok else "FAIL")
    if redis_ok is not None:
        log.info("  redis                        %s", "OK" if redis_ok else "OFF/FAIL")
    try:
        pool = pool_status()
        log.info(
            "  db pool                      size=%s checkedin=%s overflow=%s",
            pool.get("pool_size"),
            pool.get("checked_in"),
            pool.get("overflow"),
        )
    except Exception:
        pass

    if extra:
        log.info("— service details —")
        for k, v in extra.items():
            log.info("  %-28s %s", k, v)

    log.info("— api routes (%s) —", len(routes))
    for line in routes:
        log.info("  %s", line)

    log.info(bar)
    log.info("  status: %s — ready to accept traffic", status)
    log.info(bar)
