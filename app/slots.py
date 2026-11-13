"""Расчёт свободного времени.

Это чистая функция без базы данных и сети: на вход — расписание, длительность услуги
и уже занятые интервалы, на выход — список времён начала. Поэтому её легко покрыть
юнит-тестами со всеми краевыми случаями.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Schedule:
    tz: ZoneInfo
    work_start: time
    work_end: time
    work_days: frozenset[int]
    step: timedelta
    break_start: time | None = None
    break_end: time | None = None


Interval = tuple[datetime, datetime]


def _overlaps(a: Interval, b: Interval) -> bool:
    # Полуоткрытые интервалы [start, end): запись 10:00–11:00 не мешает записи 11:00–12:00
    return a[0] < b[1] and b[0] < a[1]


def free_slots(
    day: date,
    duration: timedelta,
    schedule: Schedule,
    busy: Iterable[Interval],
    not_before: datetime,
) -> list[datetime]:
    """Возвращает времена начала (в UTC), на которые можно записаться в указанный день."""
    if day.weekday() not in schedule.work_days:
        return []

    day_start = datetime.combine(day, schedule.work_start, tzinfo=schedule.tz)
    day_end = datetime.combine(day, schedule.work_end, tzinfo=schedule.tz)

    blocked: list[Interval] = list(busy)
    if schedule.break_start and schedule.break_end:
        blocked.append(
            (
                datetime.combine(day, schedule.break_start, tzinfo=schedule.tz),
                datetime.combine(day, schedule.break_end, tzinfo=schedule.tz),
            )
        )

    result: list[datetime] = []
    start = day_start
    while start + duration <= day_end:
        candidate = (start, start + duration)
        if start >= not_before and not any(_overlaps(candidate, b) for b in blocked):
            result.append(start.astimezone(UTC))
        start += schedule.step
    return result
