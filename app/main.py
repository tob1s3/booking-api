"""Точка входа: сборка приложения FastAPI."""

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.db import engine
from app.routers import auth, bookings, services

app = FastAPI(
    title="Booking API",
    description="REST API онлайн-записи к мастеру: услуги, свободное время, записи и отмены.",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(services.router)
app.include_router(bookings.router)

# /metrics для Prometheus: число запросов, задержки и коды ответов по каждому маршруту
Instrumentator(excluded_handlers=["/metrics", "/health"]).instrument(app).expose(
    app, include_in_schema=False
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Проверка живости для Docker и мониторинга: отвечает, только если доступна база."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
