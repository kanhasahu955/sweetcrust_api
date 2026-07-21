from app.routes.admin import router as admin_router
from app.routes.retailer import router as retailer_router
from app.routes.uploads import router as uploads_router
from app.routes.main import ROUTERS, mount
__all__ = ["admin_router", "retailer_router", "uploads_router", "ROUTERS", "mount"]
