"""auth-service settings = package base + auth knobs."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import SettingsConfigDict

from package.common.env import service_env_files
from package.common.settings import Settings as BaseSettings, configure_settings

_ENV_FILES = service_env_files(Path(__file__))


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    service_name: str = "auth"
    service_version: str = "0.1.0"
    port: int = Field(default=8001, validation_alias=AliasChoices("SERVICE_PORT"))
    otp_expire_minutes: int = 10
    otp_dev_code: str = "123456"

    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None

    smtp_host: Optional[str] = None
    smtp_port: int = 465
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    mail_from_name: str = "SweetCrust Bakery"
    mail_from_email: Optional[str] = None

    msg91_auth_key: Optional[str] = None
    msg91_template_id: Optional[str] = None
    msg91_sender_id: str = "SWEETCRUST"

    auth_public_base_url: str = "http://127.0.0.1:8000"
    auth_mail_notify_on_login: bool = False

    @property
    def mail_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_pass and self.mail_from_email)

    @property
    def msg91_configured(self) -> bool:
        return bool(self.msg91_auth_key and self.msg91_template_id)


@lru_cache
def get_settings() -> ServiceSettings:
    return ServiceSettings()


def reload_settings() -> ServiceSettings:
    get_settings.cache_clear()
    return get_settings()


def boot_settings() -> ServiceSettings:
    configure_settings(get_settings)
    return get_settings()
