"""Общие зависимости FastAPI."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session


def get_now() -> datetime:
    """Текущее время. Вынесено в зависимость, чтобы в тестах можно было «заморозить» часы."""
    return datetime.now(UTC)


Session = Annotated[AsyncSession, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
