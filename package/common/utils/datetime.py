"""UTC helpers for every service — prefer these over bare datetime.utcnow()."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional


def utc_now_aware() -> datetime:
    """Timezone-aware UTC (JWT exp, external APIs)."""
    return datetime.now(timezone.utc)


def utc_now() -> datetime:
    """Naive UTC datetime for SQLModel / MySQL columns in this repo."""
    return utc_now_aware().replace(tzinfo=None)


def utc_today() -> date:
    return utc_now().date()


def day_bounds(d: Optional[date] = None) -> tuple[datetime, datetime]:
    """Inclusive start and exclusive end of a UTC calendar day."""
    day = d or utc_today()
    start = datetime.combine(day, datetime.min.time())
    return start, start + timedelta(days=1)


def days_ago(n: int) -> date:
    return (utc_now() - timedelta(days=n)).date()
