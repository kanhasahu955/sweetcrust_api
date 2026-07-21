from app.routes.api import admin_router, customer_router, retailer_router, root_router
from app.routes.main import ROUTERS, mount
__all__ = ["customer_router", "admin_router", "retailer_router", "root_router", "ROUTERS", "mount"]
