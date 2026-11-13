"""Схемы запросов и ответов API (Pydantic)."""

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field

from app.models import BookingStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    phone: str | None
    is_admin: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 — это тип токена, а не пароль


class ServiceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(gt=0, le=8 * 60)
    price: int = Field(ge=0)


class ServiceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    duration_minutes: int | None = Field(default=None, gt=0, le=8 * 60)
    price: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    duration_minutes: int
    price: int
    is_active: bool


class BookingCreate(BaseModel):
    service_id: int
    # Время обязательно с часовым поясом, например 2026-11-20T10:00:00+03:00
    starts_at: AwareDatetime


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    user_id: int
    starts_at: datetime
    ends_at: datetime
    status: BookingStatus


class SlotsOut(BaseModel):
    service_id: int
    day: str
    slots: list[datetime]
