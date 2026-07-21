from app.routes.customer import router as customer_router
from app.routes.geo import router as geo_router
from app.routes.main import ROUTERS, mount
__all__ = ["customer_router", "geo_router", "ROUTERS", "mount"]
