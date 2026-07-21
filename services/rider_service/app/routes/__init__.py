from app.routes.customer import router as customer_router
from app.routes.delivery import router as delivery_router
from app.routes.main import ROUTERS, mount
__all__ = ["delivery_router", "customer_router", "ROUTERS", "mount"]
