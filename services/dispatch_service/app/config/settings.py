"""dispatch-service settings = package base + service knobs."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import SettingsConfigDict

from package.common.env import service_env_files
from package.common.settings import Settings as BaseSettings, configure_settings

_ENV_FILES = service_env_files(Path(__file__))


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    service_name: str = "dispatch"
    service_version: str = "0.1.0"
    port: int = Field(default=8019, validation_alias=AliasChoices("SERVICE_PORT"))
@lru_cache
def get_settings() -> ServiceSettings:
    return ServiceSettings()


def reload_settings() -> ServiceSettings:
    get_settings.cache_clear()
    return get_settings()


def boot_settings() -> ServiceSettings:
    configure_settings(get_settings)
    return get_settings()
