"""Бизнес-логика записи: расписание, свободные слоты, создание и отмена."""

from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import metrics
from app.config import get_settings
from app.models import Booking, BookingStatus, Service, User
from app.slots import Schedule, free_slots

EXCLUSION_VIOLATION = "23P01"  # код ошибки PostgreSQL при нарушении EXCLUDE-ограничения


def current_schedule() -> Schedule:
    s = get_settings()
    return Schedule(
        tz=s.tz,
        work_start=s.work_start,
        work_end=s.work_end,
        work_days=frozenset(s.work_days),
        step=timedelta(minutes=s.slot_step_minutes),
        break_start=s.break_start,
        break_end=s.break_end,
    )


async def get_active_service(session: AsyncSession, service_id: int) -> Service:
    service = await session.get(Service, service_id)
    if service is None or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")
    return service


async def get_free_slots(
    session: AsyncSession, service: Service, day: date, now: datetime
) -> list[datetime]:
    settings = get_settings()
    schedule = current_schedule()

    local_today = now.astimezone(schedule.tz).date()
    if day < local_today or day > local_today + timedelta(days=settings.booking_horizon_days):
        return []

    day_start = datetime.combine(day, datetime.min.time(), tzinfo=schedule.tz)
    day_end = day_start + timedelta(days=1)
    rows = await session.execute(
        select(Booking.starts_at, Booking.ends_at).where(
            Booking.status == BookingStatus.active,
            Booking.starts_at < day_end,
            Booking.ends_at > day_start,
        )
    )
    busy = [(start, end) for start, end in rows.all()]

    return free_slots(
        day=day,
        duration=timedelta(minutes=service.duration_minutes),
        schedule=schedule,
        busy=busy,
        not_before=now + timedelta(minutes=settings.min_lead_minutes),
    )


async def create_booking(
    session: AsyncSession, user: User, service_id: int, starts_at: datetime, now: datetime
) -> Booking:
    service = await get_active_service(session, service_id)
    starts_at = starts_at.astimezone(UTC)  # храним и отдаём время единообразно, в UTC
    local_day = starts_at.astimezone(get_settings().tz).date()

    # Проверка «по-хорошему»: время должно быть среди свободных слотов.
    # Она отсекает время вне расписания и даёт понятную ошибку, но не защищает от гонки.
    if starts_at not in await get_free_slots(session, service, local_day, now):
        metrics.BOOKING_CONFLICTS.inc()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Это время недоступно для записи"
        )

    booking = Booking(
        user_id=user.id,
        service_id=service.id,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=service.duration_minutes),
    )
    session.add(booking)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Гонка: другой запрос занял это время между проверкой и вставкой.
        # Её ловит EXCLUDE-ограничение в PostgreSQL.
        await session.rollback()
        if getattr(exc.orig, "sqlstate", None) == EXCLUSION_VIOLATION:
            metrics.BOOKING_CONFLICTS.inc()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Это время только что заняли"
            ) from None
        raise

    metrics.BOOKINGS_CREATED.inc()
    return booking


async def cancel_booking(
    session: AsyncSession, user: User, booking_id: int, now: datetime
) -> Booking:
    booking = await session.get(Booking, booking_id)
    # Чужую запись не показываем вовсе: 404, а не 403, чтобы не раскрывать, что она существует
    if booking is None or (booking.user_id != user.id and not user.is_admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    if booking.status == BookingStatus.cancelled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Запись уже отменена")

    if not user.is_admin:
        deadline = booking.starts_at - timedelta(hours=get_settings().cancel_deadline_hours)
        if now > deadline:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Отменить запись можно не позже, чем за "
                f"{get_settings().cancel_deadline_hours} ч до начала",
            )

    booking.status = BookingStatus.cancelled
    await session.commit()
    metrics.BOOKINGS_CANCELLED.labels(by="admin" if user.is_admin else "client").inc()
    return booking
