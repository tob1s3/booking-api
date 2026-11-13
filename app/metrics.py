"""Бизнес-метрики для Prometheus (технические метрики HTTP добавляет instrumentator в main.py)."""

from prometheus_client import Counter

BOOKINGS_CREATED = Counter("booking_bookings_created_total", "Созданные записи")
BOOKINGS_CANCELLED = Counter(
    "booking_bookings_cancelled_total", "Отменённые записи", ["by"]
)  # by = client | admin
BOOKING_CONFLICTS = Counter("booking_conflicts_total", "Попытки записаться на уже занятое время")
