from datetime import date, datetime, time, timedelta


def end_of_day_exclusive(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min)


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


def current_month_bounds(as_of: date) -> tuple[datetime, datetime]:
    return datetime.combine(month_start(as_of), time.min), end_of_day_exclusive(as_of)


def billing_cycle_bounds(billing_day: int, as_of: date) -> tuple[date, date]:
    """Return the current card cycle start and statement closing dates."""

    if as_of.day > billing_day:
        start = date(as_of.year, as_of.month, billing_day) + timedelta(days=1)
        next_month_start = next_month(as_of)
        end = date(next_month_start.year, next_month_start.month, billing_day)
        return start, end

    previous_month_start = previous_month(as_of)
    start = date(previous_month_start.year, previous_month_start.month, billing_day) + timedelta(days=1)
    end = date(as_of.year, as_of.month, billing_day)
    return start, end
