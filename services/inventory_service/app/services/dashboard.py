from __future__ import annotations

from datetime import timedelta

from sqlalchemy import case
from sqlmodel import Session, func, select

from app.models.catalog import Product
from app.models.commerce import Order, Payment, ReturnRequest
from app.models.enums import OrderStatus, PaymentStatus, StockStatus
from app.models.ops import Conversation, DeliveryTracking
from package.common.utils import day_bounds, days_ago, utc_today
from package.logger import get_logger

logger = get_logger(__name__)


def dashboard(session: Session) -> dict:
    today = utc_today()
    today_start, tomorrow_start = day_bounds(today)

    today_stats = session.exec(
        select(
            func.count(Order.id),
            func.coalesce(
                func.sum(case((Order.payment_status == PaymentStatus.PAID, Order.final_amount), else_=0)),
                0,
            ),
        ).where(Order.created_at >= today_start, Order.created_at < tomorrow_start)
    ).one()
    todays_orders = int(today_stats[0] or 0)
    revenue = float(today_stats[1] or 0)

    status_rows = session.exec(select(Order.status, func.count()).select_from(Order).group_by(Order.status)).all()
    status_counts = {row[0]: int(row[1]) for row in status_rows}

    def count_status(st: OrderStatus) -> int:
        return status_counts.get(st, 0)

    low_stock_count = session.exec(
        select(func.count()).select_from(Product).where(Product.stock_status == StockStatus.LOW_STOCK)
    ).one()
    pending_returns = session.exec(
        select(func.count()).select_from(ReturnRequest).where(ReturnRequest.status == "admin_review")
    ).one()
    unread_chats = session.exec(
        select(func.count()).select_from(Conversation).where(Conversation.unread_admin > 0)
    ).one()
    failed_payments = session.exec(
        select(func.count()).select_from(Payment).where(Payment.status == PaymentStatus.FAILED)
    ).one()

    recent_orders = list(session.exec(select(Order).order_by(Order.created_at.desc()).limit(8)).all())
    bestsellers = list(session.exec(select(Product).order_by(Product.sales_count.desc()).limit(5)).all())
    live = list(session.exec(select(DeliveryTracking)).all())
    chats = list(session.exec(select(Conversation).order_by(Conversation.updated_at.desc()).limit(5)).all())
    low_stock = list(
        session.exec(select(Product).where(Product.stock_status == StockStatus.LOW_STOCK).limit(20)).all()
    )

    series_start = today_start - timedelta(days=6)
    day_rows = session.exec(
        select(
            func.date(Order.created_at),
            func.count(Order.id),
            func.coalesce(
                func.sum(case((Order.payment_status == PaymentStatus.PAID, Order.final_amount), else_=0)),
                0,
            ),
        )
        .where(Order.created_at >= series_start)
        .group_by(func.date(Order.created_at))
    ).all()
    by_day = {str(row[0]): {"orders": int(row[1] or 0), "revenue": float(row[2] or 0)} for row in day_rows}
    series = []
    for i in range(6, -1, -1):
        d = days_ago(i)
        bucket = by_day.get(str(d), {"orders": 0, "revenue": 0.0})
        series.append({"date": str(d), "revenue": round(bucket["revenue"], 2), "orders": bucket["orders"]})

    logger.debug("dashboard cards: orders=%s revenue=%s", todays_orders, revenue)
    return {
        "cards": {
            "todays_revenue": round(revenue, 2),
            "todays_orders": todays_orders,
            "pending_orders": count_status(OrderStatus.PLACED) + count_status(OrderStatus.PAYMENT_RECEIVED),
            "preparing_orders": count_status(OrderStatus.PREPARING),
            "out_for_delivery": count_status(OrderStatus.OUT_FOR_DELIVERY),
            "delivered_orders": count_status(OrderStatus.DELIVERED),
            "pending_returns": int(pending_returns or 0),
            "unread_chats": int(unread_chats or 0),
            "low_stock_products": int(low_stock_count or 0),
            "failed_payments": int(failed_payments or 0),
        },
        "revenue_graph": series,
        "best_selling_products": bestsellers,
        "recent_orders": recent_orders,
        "live_deliveries": live,
        "latest_chats": chats,
        "low_stock": low_stock,
        "ai_insights": [],  # use ai_service /admin/insights
    }
