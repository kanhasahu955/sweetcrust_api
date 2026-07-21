from __future__ import annotations
from pathlib import Path
from app.main import create_app
REQUIRED = {"/health", "/api/v1/pricing/status", "/api/v1/pricing/quote", "/api/v1/admin/pricing/products"}
def main() -> None:
    for d in ("config", "routes", "controllers", "services", "repositories", "producers", "consumers"):
        assert (Path(__file__).resolve().parents[1] / "app" / d).is_dir(), d
    paths = set(create_app().openapi()["paths"])
    missing = sorted(REQUIRED - paths)
    assert not missing, missing
    print(f"check_pricing ok — {len(paths)} paths")
if __name__ == "__main__":
    main()
