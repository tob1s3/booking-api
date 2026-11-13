"""Юнит-тесты расчёта свободного времени: без базы и HTTP."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.slots import Schedule, free_slots

MSK = ZoneInfo("Europe/Moscow")
TUESDAY = date(2030, 1, 8)
SUNDAY = date(2030, 1, 13)
HOUR = timedelta(hours=1)
EARLY = datetime(2030, 1, 1, tzinfo=UTC)  # «сейчас» задолго до проверяемого дня

SCHEDULE = Schedule(
    tz=MSK,
    work_start=time(10, 0),
    work_end=time(20, 0),
    work_days=frozenset(range(6)),
    step=timedelta(minutes=30),
    break_start=time(14, 0),
    break_end=time(15, 0),
)


def msk(hour: int, minute: int = 0, day: date = TUESDAY) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=MSK).astimezone(UTC)


def local_times(slots: list[datetime]) -> list[str]:
    return [s.astimezone(MSK).strftime("%H:%M") for s in slots]


def test_day_off_has_no_slots():
    assert free_slots(SUNDAY, HOUR, SCHEDULE, [], EARLY) == []


def test_working_day_respects_hours_and_break():
    times = local_times(free_slots(TUESDAY, HOUR, SCHEDULE, [], EARLY))
    assert times[0] == "10:00"
    assert times[-1] == "19:00"  # часовая услуга должна закончиться к 20:00
    assert "13:00" in times  # 13:00–14:00 заканчивается ровно к перерыву
    assert "13:30" not in times and "14:00" not in times and "14:30" not in times
    assert "15:00" in times


def test_slots_are_returned_in_utc():
    slots = free_slots(TUESDAY, HOUR, SCHEDULE, [], EARLY)
    assert slots[0] == datetime(2030, 1, 8, 7, 0, tzinfo=UTC)
    assert all(s.tzinfo == UTC for s in slots)


def test_busy_interval_blocks_overlaps_but_not_neighbours():
    busy = [(msk(11), msk(12))]
    times = local_times(free_slots(TUESDAY, HOUR, SCHEDULE, busy, EARLY))
    assert "10:00" in times  # 10:00–11:00 вплотную, не пересекается
    assert "10:30" not in times and "11:00" not in times and "11:30" not in times
    assert "12:00" in times


def test_not_before_hides_past_and_too_close_slots():
    times = local_times(free_slots(TUESDAY, HOUR, SCHEDULE, [], not_before=msk(16, 10)))
    assert times[0] == "16:30"


def test_long_service_that_does_not_fit_anywhere():
    assert free_slots(TUESDAY, timedelta(hours=11), SCHEDULE, [], EARLY) == []
