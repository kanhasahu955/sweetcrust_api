"""Admin-service settings = package base + admin knobs."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import SettingsConfigDict

from package.common.env import service_env_files
from package.common.settings import Settings as BaseSettings, configure_settings

_ENV_FILES = service_env_files(Path(__file__))


class AdminSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    service_name: str = "admin"
    service_version: str = "0.1.0"
    port: int = Field(default=8107, validation_alias=AliasChoices("SERVICE_PORT"))
    bakery_upi_id: str = "sweetcrust@upi"

    imagekit_public_key: Optional[str] = None
    imagekit_private_key: Optional[str] = None
    imagekit_url_endpoint: Optional[str] = None

    razorpay_key_id: Optional[str] = None
    razorpay_key_secret: Optional[str] = None
    razorpay_webhook_secret: Optional[str] = None

    @property
    def imagekit_configured(self) -> bool:
        return bool(self.imagekit_public_key and self.imagekit_private_key and self.imagekit_url_endpoint)

    @property
    def razorpay_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)


@lru_cache
def get_settings() -> AdminSettings:
    return AdminSettings()


def reload_settings() -> AdminSettings:
    get_settings.cache_clear()
    return get_settings()


def boot_settings() -> AdminSettings:
    configure_settings(get_settings)
    return get_settings()
