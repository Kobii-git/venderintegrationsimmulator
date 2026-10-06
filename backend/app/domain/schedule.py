from typing import Any

from app.core.config import Settings
from app.core.exceptions import ValidationAppError
from app.domain.enums import ScheduleType


def validate_schedule_config(schedule: dict[str, Any], settings: Settings) -> None:
    raw_type = schedule.get("type", ScheduleType.MANUAL.value)
    schedule_type = ScheduleType.CONTINUOUS if raw_type == "interval" else ScheduleType(raw_type)

    if schedule_type == ScheduleType.MANUAL:
        return

    rate = schedule.get("events_per_second")
    interval = schedule.get("interval_seconds")
    if rate is not None:
        if interval is not None or not 0.1 <= float(rate) <= 100:
            raise ValidationAppError("Use either interval_seconds or events_per_second (0.1–100)")
    else:
        if interval is None:
            raise ValidationAppError("interval_seconds is required for scheduled simulations")
        if (
            not settings.scheduler_min_interval_seconds
            <= interval
            <= settings.scheduler_max_interval_seconds
        ):
            raise ValidationAppError(
                f"interval_seconds must be at least {settings.scheduler_min_interval_seconds} "
                f"and at most {settings.scheduler_max_interval_seconds}"
            )

    if schedule_type == ScheduleType.FINITE:
        event_count = schedule.get("event_count")
        if event_count is None:
            raise ValidationAppError("event_count is required for finite simulations")
        if event_count > settings.scheduler_max_event_count:
            raise ValidationAppError(
                f"event_count must be at most {settings.scheduler_max_event_count}"
            )
