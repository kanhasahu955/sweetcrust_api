"""Credentials for backend_v2 only — never reads legacy ``backend/``.

Canonical file: ``backend_v2/.env``
"""
from __future__ import annotations

from pathlib import Path

# package/common/env.py → backend_v2/
V2_ROOT = Path(__file__).resolve().parents[2]
ROOT_ENV = V2_ROOT / ".env"

# Back-compat alias used by check_package / older imports
BACKEND_ENV = ROOT_ENV


def package_env_files() -> tuple[str, ...]:
    """Env files for package ``Settings``. Later entries win."""
    return (".env", str(ROOT_ENV))


def service_env_files(settings_py: Path) -> tuple[str, ...]:
    """Env files for a service ``app/config/settings.py``.

    Order: cwd ``.env`` → service-local ``.env`` → ``backend_v2/.env`` (wins).
    """
    service_root = settings_py.resolve().parents[2]
    return (
        ".env",
        str(service_root / ".env"),
        str(ROOT_ENV),
    )
