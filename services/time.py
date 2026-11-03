"""Application timezone helpers."""
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

APP_TZ_NAME = os.environ.get("APP_TIMEZONE", "Australia/Melbourne")


def app_now():
    try:
        return datetime.now(ZoneInfo(APP_TZ_NAME))
    except Exception:
        return datetime.now()


def app_today():
    return app_now().date()


def local_day_bounds_utc(day):
    try:
        start_local = datetime.combine(day, datetime.min.time()).replace(tzinfo=ZoneInfo(APP_TZ_NAME))
        end_local = start_local + timedelta(days=1)
        return (start_local.astimezone(timezone.utc).replace(tzinfo=None),
                end_local.astimezone(timezone.utc).replace(tzinfo=None))
    except Exception:
        start = datetime.combine(day, datetime.min.time())
        return start, start + timedelta(days=1)


def local_date_of(dt):
    try:
        return dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(APP_TZ_NAME)).date()
    except Exception:
        return dt.date()
