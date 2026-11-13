from datetime import date, datetime, timedelta

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.booking_service import cancel_booking, create_booking
from app.config import get_settings
from app.deps import Now, Session
from app.models import Booking, BookingStatus
from app.schemas import BookingCreate, BookingOut
from app.security import AdminUser, CurrentUser

router = APIRouter(tags=["bookings"])


@router.post("/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def book(data: BookingCreate, session: Session, user: CurrentUser, now: Now) -> Booking:
    return await create_booking(session, user, data.service_id, data.starts_at, now)


@router.get("/bookings/me", response_model=list[BookingOut])
async def my_bookings(
    session: Session, user: CurrentUser, now: Now, include_past: bool = False
) -> list[Booking]:
    query = select(Booking).where(Booking.user_id == user.id).order_by(Booking.starts_at)
    if not include_past:
        query = query.where(Booking.ends_at > now)
    return list(await session.scalars(query))


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
async def cancel(booking_id: int, session: Session, user: CurrentUser, now: Now) -> Booking:
    return await cancel_booking(session, user, booking_id, now)


@router.get("/admin/schedule", response_model=list[BookingOut], tags=["admin"])
async def admin_schedule(
    session: Session,
    _: AdminUser,
    date_from: date,
    days: int = Query(default=1, ge=1, le=31),
) -> list[Booking]:
    """Активные записи на `days` дней, начиная с `date_from` (по времени заведения)."""
    tz = get_settings().tz
    start = datetime.combine(date_from, datetime.min.time(), tzinfo=tz)
    end = start + timedelta(days=days)
    result = await session.scalars(
        select(Booking)
        .where(
            Booking.status == BookingStatus.active,
            Booking.starts_at >= start,
            Booking.starts_at < end,
        )
        .order_by(Booking.starts_at)
    )
    return list(result)
