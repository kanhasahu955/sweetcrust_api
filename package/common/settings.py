"""Shared settings for ALL FastAPI services.

Services call `configure_settings(factory)` at boot so DB/CORS/JWT/logging
use that service's Settings subclass (e.g. AISettings).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional, TypeVar

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from package.common.env import package_env_files

T = TypeVar("T", bound="Settings")
_factory: Callable[[], Settings] | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=package_env_files(), extra="ignore")

    # --- service identity ---
    app_name: str = "SweetCrust Bakery"
    service_name: str = "service"
    service_version: str = "0.1.0"
    env: str = "development"
    host: str = "0.0.0.0"
    # Ignore root .env PORT=8000 (shared file) — use SERVICE_PORT or class default.
    # Docker compose / uvicorn CLI still bind via process env PORT separately.
    port: int = Field(default=8000, validation_alias=AliasChoices("SERVICE_PORT"))
    reload: bool = True

    # --- logging ---
    log_level: str = "INFO"
    log_json: bool = False
    log_color: bool = True
    request_log: bool = True

    # --- database (primary + optional read replica / LB VIP) ---
    database_url: str = "mysql+pymysql://root@127.0.0.1:3306/sweetcrust"
    database_read_url: Optional[str] = None  # replica or load-balancer read endpoint
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    db_echo: bool = False
    db_log_slow_ms: int = 0  # 0 = off; e.g. 200 logs slow queries

    # --- auth ---
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # --- http ---
    cors_origins: str = "*"
    # Relative paths resolve to backend_v2/uploads so auth write + store-ops serve share one dir.
    upload_dir: str = "uploads"

    # --- realtime / cache ---
    redis_url: Optional[str] = None

    # --- bakery profile (shared copy) ---
    bakery_name: str = "SweetCrust Bakery"
    bakery_phone: str = "+919876543210"
    bakery_gstin: Optional[str] = None
    bakery_upi_id: Optional[str] = None

    # --- SMTP (invoice / auth mail) ---
    smtp_host: Optional[str] = None
    smtp_port: int = 465
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    mail_from_name: str = "SweetCrust Bakery"
    mail_from_email: Optional[str] = None

    @model_validator(mode="after")
    def _resolve_upload_dir(self):
        p = Path(self.upload_dir)
        if not p.is_absolute():
            # package/common/settings.py → backend_v2
            root = Path(__file__).resolve().parents[2]
            object.__setattr__(self, "upload_dir", str((root / p).resolve()))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.env.lower() in ("development", "dev", "local")

    @property
    def redis_configured(self) -> bool:
        return bool(self.redis_url)

    @property
    def mail_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_pass and self.mail_from_email)

    def public_dict(self) -> dict:
        """Non-secret snapshot for /health or boot logs."""
        return {
            "app_name": self.app_name,
            "service_name": self.service_name,
            "service_version": self.service_version,
            "env": self.env,
            "host": self.host,
            "port": self.port,
            "log_level": self.log_level,
            "log_json": self.log_json,
            "db_pool_size": self.db_pool_size,
            "db_has_read_replica": bool(self.database_read_url),
            "redis": self.redis_configured,
            "cors": self.cors_origins,
        }


def configure_settings(factory: Callable[[], Settings]) -> None:
    """Register the active settings provider (call before first DB access)."""
    global _factory
    _factory = factory
    get_settings.cache_clear()


@lru_cache
def get_settings() -> Settings:
    if _factory is not None:
        return _factory()
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
