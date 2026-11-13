"""Настройки приложения. Все значения читаются из переменных окружения или файла .env."""

from datetime import time
from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5432/booking"

    # JWT. Секрет обязательно переопределить в .env: значение по умолчанию только для разработки.
    jwt_secret: str = Field(default="change-me-in-production", min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Расписание. Время работы задаётся в часовом поясе заведения, в базе всё хранится в UTC.
    timezone: str = "Europe/Moscow"
    work_start: time = time(10, 0)
    work_end: time = time(20, 0)
    break_start: time | None = time(14, 0)
    break_end: time | None = time(15, 0)
    work_days: Annotated[list[int], NoDecode] = [0, 1, 2, 3, 4, 5]  # 0 = понедельник
    slot_step_minutes: int = 30
    min_lead_minutes: int = 60  # нельзя записаться ближе, чем за час до начала
    booking_horizon_days: int = 30  # и дальше, чем на 30 дней вперёд
    cancel_deadline_hours: int = 3  # клиент может отменить запись не позже, чем за 3 часа

    @field_validator("work_days", mode="before")
    @classmethod
    def parse_work_days(cls, value: object) -> object:
        # Позволяет писать в .env: WORK_DAYS=0,1,2,3,4
        if isinstance(value, str):
            return [int(part) for part in value.split(",") if part.strip()]
        return value

    @field_validator("break_start", "break_end", mode="before")
    @classmethod
    def empty_break_means_none(cls, value: object) -> object:
        # BREAK_START= (пустое значение) отключает перерыв
        return None if value == "" else value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
