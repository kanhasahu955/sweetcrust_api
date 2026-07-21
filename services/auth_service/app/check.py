"""ponytail: OpenAPI surface. Run: python -m app.check"""
from __future__ import annotations

from pathlib import Path

from app.main import create_app

REQUIRED = {
    "/health",
    "/api/v1/auth/otp/send",
    "/api/v1/auth/otp/verify",
    "/api/v1/auth/google",
    "/api/v1/auth/google/setup",
    "/api/v1/auth/google/start",
    "/api/v1/auth/google/callback",
    "/api/v1/auth/google/finish",
    "/api/v1/auth/guest",
    "/api/v1/auth/admin/registration-status",
    "/api/v1/auth/admin/register",
    "/api/v1/auth/admin/confirm-email",
    "/api/v1/auth/admin/resend-confirmation",
    "/api/v1/auth/admin/login",
    "/api/v1/auth/admin/otp",
    "/api/v1/auth/delivery/login",
    "/api/v1/auth/retailer/upload",
    "/api/v1/auth/retailer/upload-base64",
    "/api/v1/auth/retailer/otp/verify",
    "/api/v1/auth/retailer/google",
    "/api/v1/auth/retailer/google/setup",
    "/api/v1/auth/retailer/google/start",
    "/api/v1/auth/retailer/google/callback",
    "/api/v1/auth/retailer/google/finish",
    "/api/v1/auth/retailer/login",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "main.py").is_file()
    assert (root / "app").is_dir()
    assert (root / "app" / "config").is_dir()
    assert (root / "app" / "routes").is_dir()
    assert (root / "app" / "controllers").is_dir()
    assert (root / "app" / "services").is_dir()
    assert (root / "app" / "repositories").is_dir()
    assert (root / "app" / "producers").is_dir()
    assert (root / "app" / "consumers").is_dir()
    assert not (root / "models").exists(), "models/ must live under app/"

    app = create_app()
    paths = set(app.openapi()["paths"])
    missing = sorted(REQUIRED - paths)
    assert not missing, missing
    print(f"check_auth ok — {len(paths)} paths, {len(REQUIRED)} required")


if __name__ == "__main__":
    main()
