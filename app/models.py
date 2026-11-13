"""Таблицы базы данных."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="ck_services_duration_positive"),
        CheckConstraint("price >= 0", name="ck_services_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)  # в рублях
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class BookingStatus(enum.StrEnum):
    active = "active"
    cancelled = "cancelled"


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_bookings_period_valid"),
        # Главная защита от двойной записи: PostgreSQL сам не даст сохранить две
        # активные записи с пересекающимися интервалами времени, даже если два
        # запроса придут одновременно. Проверка в коде — только для понятного ответа.
        ExcludeConstraint(
            (func.tstzrange(text("starts_at"), text("ends_at"), text("'[)'")), "&&"),
            name="ex_bookings_no_overlap",
            using="gist",
            where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        default=BookingStatus.active,
        server_default=BookingStatus.active.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="bookings")
    service: Mapped[Service] = relationship()
