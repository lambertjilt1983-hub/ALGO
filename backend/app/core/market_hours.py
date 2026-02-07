from __future__ import annotations

from datetime import date, datetime, time
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import get_settings

DEFAULT_TZ = "Asia/Kolkata"


def _market_tz() -> ZoneInfo:
    settings = get_settings()
    tz_name = getattr(settings, "MARKET_TIMEZONE", DEFAULT_TZ) or DEFAULT_TZ
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def ist_now() -> datetime:
    return datetime.now(tz=_market_tz())


@lru_cache(maxsize=1)
def _holiday_set() -> set[date]:
    settings = get_settings()
    raw = getattr(settings, "MARKET_HOLIDAYS", "") or ""
    holidays: set[date] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            holidays.add(date.fromisoformat(item))
        except ValueError:
            continue
    return holidays


def is_market_holiday(day: date) -> bool:
    return day in _holiday_set()


def is_trading_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    return not is_market_holiday(day)


def is_market_open(start: time, end: time, now: datetime | None = None) -> bool:
    current = now or ist_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=_market_tz())
    if not is_trading_day(current.date()):
        return False
    return start <= current.time() <= end


def is_after_close(close_time: time, now: datetime | None = None) -> bool:
    current = now or ist_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=_market_tz())
    if not is_trading_day(current.date()):
        return False
    return current.time() >= close_time
