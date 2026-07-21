"""Deprecated shim — use package.common instead.

Kept so older stubs (`auth/main.py` etc.) keep importing without breakage.
"""
from __future__ import annotations

from package.common.factory import create_service_app
from package.common.lifecycle import service_lifespan
from package.common.middleware import setup_middleware
from package.common.settings import get_settings


def create_service(name: str, version: str = "0.1.0"):
    """Legacy helper used by stub services."""
    from package.common.settings import configure_settings
    from package.common.settings import Settings

    class _S(Settings):
        service_name: str = name
        service_version: str = version

    configure_settings(_S)
    return create_service_app(title=f"SweetCrust {name}", version=version)


__all__ = ["create_service", "create_service_app", "setup_middleware", "service_lifespan", "get_settings"]
