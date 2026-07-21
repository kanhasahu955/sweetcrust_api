from app.routes.customer import router as customer_router
from app.routes.payments import router as payments_router

__all__ = ["payments_router", "customer_router"]
