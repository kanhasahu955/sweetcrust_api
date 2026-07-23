"""Shop open-hours helpers (IST). Auto-close when outside schedule."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

SHOP_TZ = ZoneInfo("Asia/Kolkata")

_DAY_ALIASES = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


def parse_hhmm(raw: str | None, default: time) -> time:
    s = (raw or "").strip()
    if not s:
        return default
    try:
        parts = s.replace(".", ":").split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return time(h, m)
    except (TypeError, ValueError):
        pass
    return default


def _day_allowed(shop_days: str | None, weekday: int) -> bool:
    """weekday: Mon=0 … Sun=6 (Python datetime)."""
    raw = (shop_days or "").strip()
    if not raw:
        return True
    key = raw.lower().replace(" ", "")
    if key in {"mon-sun", "daily", "all", "everyday", "alldays"}:
        return True
    # Range like Mon-Fri / Mon-Sat
    if "-" in key and "," not in key:
        a, _, b = key.partition("-")
        start = _DAY_ALIASES.get(a)
        end = _DAY_ALIASES.get(b)
        if start is not None and end is not None:
            if start <= end:
                return start <= weekday <= end
            return weekday >= start or weekday <= end
    tokens = [t for t in key.replace("/", ",").split(",") if t]
    allowed = {_DAY_ALIASES[t] for t in tokens if t in _DAY_ALIASES}
    if not allowed:
        return True
    return weekday in allowed


def is_within_shop_hours(
    shop_open_time: str | None,
    shop_close_time: str | None,
    shop_days: str | None = None,
    *,
    now: datetime | None = None,
) -> bool:
    """True when current IST time is on an open day and in [open, close)."""
    now = now or datetime.now(SHOP_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=SHOP_TZ)
    else:
        now = now.astimezone(SHOP_TZ)
    if not _day_allowed(shop_days, now.weekday()):
        return False
    open_t = parse_hhmm(shop_open_time, time(9, 0))
    close_t = parse_hhmm(shop_close_time, time(21, 0))
    cur = now.timetz().replace(tzinfo=None)
    if open_t == close_t:
        return True  # 24h
    if open_t < close_t:
        return open_t <= cur < close_t
    # Overnight window e.g. 22:00–06:00
    return cur >= open_t or cur < close_t


def profile_within_hours(profile: Any, *, now: datetime | None = None) -> bool:
    return is_within_shop_hours(
        getattr(profile, "shop_open_time", None),
        getattr(profile, "shop_close_time", None),
        getattr(profile, "shop_days", None),
        now=now,
    )


def enforce_auto_close(profile: Any, *, now: datetime | None = None) -> bool:
    """If outside hours and is_open, set is_open=False. Returns True when changed."""
    if not getattr(profile, "is_open", False):
        return False
    if profile_within_hours(profile, now=now):
        return False
    profile.is_open = False
    return True


def _self_check() -> None:
    from datetime import timezone

    # Fixed IST Tuesday 10:30 → inside 09:00–21:00
    noonish = datetime(2026, 7, 21, 5, 0, tzinfo=timezone.utc)  # 10:30 IST
    assert is_within_shop_hours("09:00", "21:00", "Mon-Sun", now=noonish)
    late = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)  # 21:30 IST
    assert not is_within_shop_hours("09:00", "21:00", "Mon-Sun", now=late)
    # Exact close → closed
    close_exact = datetime(2026, 7, 21, 15, 30, tzinfo=timezone.utc)  # 21:00 IST
    assert not is_within_shop_hours("09:00", "21:00", "Mon-Sun", now=close_exact)
    # Sunday excluded
    sun = datetime(2026, 7, 19, 5, 0, tzinfo=timezone.utc)  # Sun 10:30 IST
    assert not is_within_shop_hours("09:00", "21:00", "Mon-Sat", now=sun)
    print("shop_hours ok")


if __name__ == "__main__":
    _self_check()
