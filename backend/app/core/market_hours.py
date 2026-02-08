from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo
import requests

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


def _nse_market_open() -> bool | None:
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/",
    }
    try:
        session.get("https://www.nseindia.com", headers=headers, timeout=5)
        resp = session.get("https://www.nseindia.com/api/marketStatus", headers=headers, timeout=5)
        resp.raise_for_status()
        payload = resp.json()
        print("[DEBUG] NSE /api/marketStatus response:", payload, flush=True)
    except Exception as e:
        print(f"[DEBUG] NSE /api/marketStatus error: {e}", flush=True)
        return None

    for entry in payload.get("marketState", []) or []:
        if str(entry.get("market")) == "Capital Market":
            print("[DEBUG] NSE Capital Market entry:", entry, flush=True)
            status = str(entry.get("marketStatus") or "").lower()
            if status:
                print(f"[DEBUG] NSE Capital Market status: {status}", flush=True)
                return status == "open"
            break

    return None


def _nse_last_update(now: datetime) -> datetime | None:
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/",
    }
    try:
        session.get("https://www.nseindia.com", headers=headers, timeout=5)
        resp = session.get("https://www.nseindia.com/api/allIndices", headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json().get("data") or []
        print("[DEBUG] NSE /api/allIndices data:", data, flush=True)
    except Exception as e:
        print(f"[DEBUG] NSE /api/allIndices error: {e}", flush=True)
        return None

    row = next((item for item in data if item.get("index") == "NIFTY 50"), None)
    if not row:
        return None

    last_update = row.get("lastUpdateTime") or row.get("timestamp")
    if not last_update:
        return None

    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"):
        try:
            parsed = datetime.strptime(last_update, fmt)
            return parsed.replace(tzinfo=now.tzinfo or _market_tz())
        except ValueError:
            continue

    return None


def market_status(start: time, end: time, now: datetime | None = None) -> dict:
    current = now or ist_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=_market_tz())

    nse_open = _nse_market_open()
    if nse_open is True:
        return {
            "is_open": True,
            "reason": "Open (NSE status)",
            "current_date": current.date().isoformat(),
            "current_time": current.time().strftime("%H:%M"),
        }
    if nse_open is False:
        return {
            "is_open": False,
            "reason": "Closed (NSE status)",
            "current_date": current.date().isoformat(),
            "current_time": current.time().strftime("%H:%M"),
        }

    nse_last = _nse_last_update(current)
    if nse_last:
        within_window = start <= nse_last.time() <= end
        recent = (current - nse_last) <= timedelta(minutes=30)
        if within_window and recent:
            return {
                "is_open": True,
                "reason": "Open (NSE)",
                "current_date": current.date().isoformat(),
                "current_time": current.time().strftime("%H:%M"),
            }

    today = current.date()
    if today.weekday() >= 5:
        return {
            "is_open": False,
            "reason": "Weekend",
            "current_date": today.isoformat(),
            "current_time": current.time().strftime("%H:%M"),
        }
    if is_market_holiday(today):
        return {
            "is_open": False,
            "reason": "Holiday",
            "current_date": today.isoformat(),
            "current_time": current.time().strftime("%H:%M"),
        }

    current_time = current.time()
    if current_time < start:
        return {
            "is_open": False,
            "reason": "Before market open",
            "current_date": today.isoformat(),
            "current_time": current_time.strftime("%H:%M"),
        }
    if current_time > end:
        return {
            "is_open": False,
            "reason": "After market close",
            "current_date": today.isoformat(),
            "current_time": current_time.strftime("%H:%M"),
        }

    return {
        "is_open": True,
        "reason": "Open",
        "current_date": today.isoformat(),
        "current_time": current_time.strftime("%H:%M"),
    }
