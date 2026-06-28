from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from app.db.models.query_library import ScheduleConfig
from app.db.repositories import dashboard_repository, query_library_repository


WidgetCadence = Literal["hourly", "daily", "weekly", "monthly"]
WIDGET_MANUAL_ONLY = "Manual only"

_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime | None) -> datetime:
    current = value or _utcnow()
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _next_daily_run(current_local: datetime, config: ScheduleConfig) -> datetime:
    candidate = current_local.replace(
        hour=config.hour,
        minute=config.minute,
        second=0,
        microsecond=0,
    )
    if candidate <= current_local:
        candidate += timedelta(days=1)
    return candidate


def _next_weekly_run(current_local: datetime, config: ScheduleConfig) -> datetime:
    target_weekday = _WEEKDAY_INDEX.get((config.day_of_week or "monday").lower(), 0)
    base = current_local.replace(
        hour=config.hour,
        minute=config.minute,
        second=0,
        microsecond=0,
    )
    day_delta = (target_weekday - base.weekday()) % 7
    candidate = base + timedelta(days=day_delta)
    if candidate <= current_local:
        candidate += timedelta(days=7)
    return candidate


def _next_monthly_run(current_local: datetime, config: ScheduleConfig) -> datetime:
    target_day = max(1, int(config.day_of_month or 1))
    year = current_local.year
    month = current_local.month

    for _ in range(24):
        days_in_month = monthrange(year, month)[1]
        if target_day <= days_in_month:
            candidate = current_local.replace(
                year=year,
                month=month,
                day=target_day,
                hour=config.hour,
                minute=config.minute,
                second=0,
                microsecond=0,
            )
            if candidate > current_local:
                return candidate
        month += 1
        if month > 12:
            month = 1
            year += 1

    raise ValueError("Could not compute the next monthly run.")


def compute_next_saved_query_run(
    config: ScheduleConfig | None,
    *,
    now: datetime | None = None,
) -> datetime | None:
    if not config or not config.enabled:
        return None

    current_utc = _coerce_utc(now)
    zone = ZoneInfo(config.timezone)
    current_local = current_utc.astimezone(zone)

    if config.frequency == "daily":
        next_local = _next_daily_run(current_local, config)
    elif config.frequency == "weekly":
        next_local = _next_weekly_run(current_local, config)
    elif config.frequency == "monthly":
        next_local = _next_monthly_run(current_local, config)
    else:
        raise ValueError(f"Unsupported schedule frequency: {config.frequency}")

    return next_local.astimezone(timezone.utc)


def parse_widget_cadence(cadence: str | None) -> WidgetCadence | None:
    if not cadence:
        return None
    cadence_lower = cadence.strip().lower()
    if cadence_lower == WIDGET_MANUAL_ONLY.lower():
        return None
    for supported in ("hourly", "daily", "weekly", "monthly"):
        if supported in cadence_lower:
            return supported
    return None


def compute_next_widget_run(cadence: str | None, *, now: datetime | None = None) -> datetime | None:
    cadence_key = parse_widget_cadence(cadence)
    if cadence_key is None:
        return None

    current = _coerce_utc(now)
    base = current.replace(second=0, microsecond=0)

    if cadence_key == "hourly":
        return base.replace(minute=0) + timedelta(hours=1)
    if cadence_key == "daily":
        candidate = base.replace(hour=0, minute=0)
        if candidate <= current:
            candidate += timedelta(days=1)
        return candidate
    if cadence_key == "weekly":
        candidate = base.replace(hour=0, minute=0)
        days_until_monday = (7 - candidate.weekday()) % 7
        candidate += timedelta(days=days_until_monday)
        if candidate <= current:
            candidate += timedelta(days=7)
        return candidate
    if cadence_key == "monthly":
        year = current.year
        month = current.month
        candidate = base.replace(day=1, hour=0, minute=0)
        if candidate <= current:
            month += 1
            if month > 12:
                month = 1
                year += 1
            candidate = candidate.replace(year=year, month=month, day=1)
        return candidate

    return None


async def sync_saved_query_runtime(user_id: str, query_id: str, schedule: ScheduleConfig | None) -> None:
    next_run_at = compute_next_saved_query_run(schedule)
    await query_library_repository.set_schedule_runtime_state(
        user_id,
        query_id,
        next_run_at=next_run_at,
        last_run_status=None,
        last_error=None,
    )


async def clear_saved_query_runtime(user_id: str, query_id: str) -> None:
    await query_library_repository.set_schedule_runtime_state(
        user_id,
        query_id,
        next_run_at=None,
        last_run_status=None,
        last_error=None,
    )


async def sync_widget_runtime(user_id: str, widget_id: str, cadence: str | None) -> None:
    next_run_at = compute_next_widget_run(cadence)
    await dashboard_repository.set_widget_schedule_runtime_state(
        user_id,
        widget_id,
        next_run_at=next_run_at,
        last_run_status=None,
        last_error=None,
    )


async def clear_widget_runtime(user_id: str, widget_id: str) -> None:
    await dashboard_repository.set_widget_schedule_runtime_state(
        user_id,
        widget_id,
        next_run_at=None,
        last_run_status=None,
        last_error=None,
    )
