"""ponytail: OpenAPI surface. Run: python -m app.check"""
from __future__ import annotations

from pathlib import Path

from app.main import create_app

REQUIRED = {
    "/api/v1/customer/home",
    "/api/v1/customer/categories",
    "/api/v1/customer/brands",
    "/api/v1/customer/products",
    "/api/v1/customer/products/{product_id}",
    "/api/v1/customer/products/{product_id}/favorite",
    "/api/v1/customer/products/{product_id}/reviews",
    "/api/v1/geo/suggest",
    "/api/v1/geo/place/{place_id}",
    "/api/v1/geo/reverse",
    "/api/v1/geo/pincode/{pin}",
    "/health",
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
    print(f"check_catalog ok — {len(paths)} paths")


if __name__ == "__main__":
    main()
