from __future__ import annotations
from pathlib import Path
from app.main import create_app
REQUIRED = {"/health", "/api/v1/assortment/status", "/api/v1/admin/assortment/products", "/api/v1/retailer/assortment"}
def main() -> None:
    for d in ("config", "routes", "controllers", "services", "repositories", "producers", "consumers"):
        assert (Path(__file__).resolve().parents[1] / "app" / d).is_dir(), d
    missing = sorted(REQUIRED - set(create_app().openapi()["paths"]))
    assert not missing, missing
    print(f"check_assortment ok — {len(create_app().openapi()['paths'])} paths")
if __name__ == "__main__":
    main()
