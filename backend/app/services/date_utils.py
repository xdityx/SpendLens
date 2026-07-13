from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings

UTC = timezone.utc


def get_app_timezone() -> ZoneInfo:
    return get_settings().app_zoneinfo


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _utc_naive_to_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC)


def normalize_transaction_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=get_app_timezone())
    return value.astimezone(UTC).replace(tzinfo=None)


def current_app_date() -> date:
    return _utc_naive_to_aware(utc_now_naive()).astimezone(get_app_timezone()).date()


def app_date_start_utc_naive(day: date) -> datetime:
    local_start = datetime.combine(day, time.min, tzinfo=get_app_timezone())
    return local_start.astimezone(UTC).replace(tzinfo=None)


def app_date_end_exclusive_utc_naive(day: date) -> datetime:
    return app_date_start_utc_naive(day + timedelta(days=1))


def end_of_day_exclusive(day: date) -> datetime:
    return app_date_end_exclusive_utc_naive(day)


def month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def next_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def previous_month(day: date) -> date:
    if day.month == 1:
        return date(day.year - 1, 12, 1)
    return date(day.year, day.month - 1, 1)


def current_month_utc_bounds(as_of: date) -> tuple[datetime, datetime]:
    return app_date_start_utc_naive(month_start(as_of)), app_date_end_exclusive_utc_naive(as_of)


def full_month_utc_bounds(day: date) -> tuple[datetime, datetime]:
    start = month_start(day)
    return app_date_start_utc_naive(start), app_date_start_utc_naive(next_month(start))


def app_local_date_from_utc_naive(value: datetime) -> date:
    return _utc_naive_to_aware(value).astimezone(get_app_timezone()).date()


def current_month_bounds(as_of: date) -> tuple[datetime, datetime]:
    return current_month_utc_bounds(as_of)


def billing_cycle_bounds(billing_day: int, as_of: date) -> tuple[date, date]:
    """Return the inclusive current card cycle range in app-local dates."""

    if as_of.day >= billing_day:
        start = date(as_of.year, as_of.month, billing_day)
        next_month_start = next_month(as_of)
        end = date(next_month_start.year, next_month_start.month, billing_day) - timedelta(days=1)
        return start, end

    previous_month_start = previous_month(as_of)
    start = date(previous_month_start.year, previous_month_start.month, billing_day)
    end = date(as_of.year, as_of.month, billing_day) - timedelta(days=1)
    return start, end


def billing_cycle_utc_bounds(billing_day: int, as_of: date) -> tuple[datetime, datetime]:
    cycle_start, _cycle_end = billing_cycle_bounds(billing_day, as_of)
    return app_date_start_utc_naive(cycle_start), app_date_end_exclusive_utc_naive(as_of)
