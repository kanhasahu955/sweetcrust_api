"""ponytail: OpenAPI surface + haversine sanity. Run: python -m app.check"""
from __future__ import annotations

from pathlib import Path

from app.main import create_app
from package.common.utils import haversine_km

REQUIRED = {
    "/api/v1/delivery/me",
    "/api/v1/delivery/orders",
    "/api/v1/delivery/availability",
    "/api/v1/delivery/location",
    "/api/v1/delivery/orders/{order_id}/delivered",
    "/api/v1/customer/delivery/check",
    "/health",
}


def _haversine_check() -> None:
    # ~0 km same point; Andheri→Bandra roughly 5–10 km
    assert haversine_km(19.1197, 72.8468, 19.1197, 72.8468) == 0.0
    d = haversine_km(19.1197, 72.8468, 19.0596, 72.8295)
    assert 5.0 < d < 12.0, d


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

    _haversine_check()

    app = create_app()
    paths = set(app.openapi()["paths"])
    missing = sorted(REQUIRED - paths)
    assert not missing, missing
    print(f"check_delivery ok — {len(paths)} paths")


if __name__ == "__main__":
    main()
