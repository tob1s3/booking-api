import asyncio
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Booking
from tests.conftest import FIXED_NOW

TUESDAY_10_MSK = "2030-01-08T10:00:00+03:00"


async def book(client, headers, service_id, starts_at=TUESDAY_10_MSK):
    return await client.post(
        "/bookings", json={"service_id": service_id, "starts_at": starts_at}, headers=headers
    )


async def test_booking_takes_the_slot(client, user_headers, haircut):
    resp = await book(client, user_headers, haircut.id)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "active"
    assert body["ends_at"] == "2030-01-08T08:00:00Z"  # 11:00 по Москве

    slots = (await client.get(f"/services/{haircut.id}/slots?day=2030-01-08")).json()["slots"]
    assert "2030-01-08T07:00:00Z" not in slots
    assert "2030-01-08T07:30:00Z" not in slots  # 10:30–11:30 пересекается с записью

    mine = (await client.get("/bookings/me", headers=user_headers)).json()
    assert [b["id"] for b in mine] == [body["id"]]


async def test_taken_slot_cannot_be_booked_again(client, user_headers, other_user_headers, haircut):
    assert (await book(client, user_headers, haircut.id)).status_code == 201
    assert (await book(client, other_user_headers, haircut.id)).status_code == 409


@pytest.mark.parametrize(
    "starts_at",
    [
        "2030-01-08T10:15:00+03:00",  # не по сетке расписания
        "2030-01-08T14:00:00+03:00",  # перерыв
        "2030-01-08T19:30:00+03:00",  # не успеет закончиться до 20:00
        "2030-01-13T12:00:00+03:00",  # воскресенье — выходной
        "2030-01-07T10:30:00+03:00",  # меньше чем за час от «сейчас» (10:00)
    ],
)
async def test_time_outside_schedule_is_rejected(client, user_headers, haircut, starts_at):
    assert (await book(client, user_headers, haircut.id, starts_at)).status_code == 409


async def test_time_without_timezone_is_rejected(client, user_headers, haircut):
    assert (await book(client, user_headers, haircut.id, "2030-01-08T10:00:00")).status_code == 422


async def test_concurrent_requests_get_exactly_one_booking(
    client, user_headers, other_user_headers, haircut
):
    results = await asyncio.gather(
        *[book(client, h, haircut.id) for h in (user_headers, other_user_headers) * 3]
    )
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409, 409, 409, 409, 409]


async def test_database_rejects_overlap_even_without_api_checks(user_headers, haircut):
    """Проверяем саму защиту в PostgreSQL, минуя API: пересекающиеся записи не сохранить."""
    start = FIXED_NOW + timedelta(days=1)
    async with SessionLocal() as session:
        session.add(
            Booking(
                user_id=1,
                service_id=haircut.id,
                starts_at=start,
                ends_at=start + timedelta(hours=1),
            )
        )
        await session.commit()
        session.add(
            Booking(
                user_id=1,
                service_id=haircut.id,
                starts_at=start + timedelta(minutes=30),
                ends_at=start + timedelta(minutes=90),
            )
        )
        with pytest.raises(IntegrityError, match="ex_bookings_no_overlap"):
            await session.commit()


async def test_client_cancels_in_time_and_slot_is_freed(client, user_headers, haircut):
    booking_id = (await book(client, user_headers, haircut.id)).json()["id"]

    resp = await client.post(f"/bookings/{booking_id}/cancel", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    assert (
        await client.post(f"/bookings/{booking_id}/cancel", headers=user_headers)
    ).status_code == 409

    # Время снова свободно, и на него можно записаться
    assert (await book(client, user_headers, haircut.id)).status_code == 201


async def test_client_cannot_cancel_too_late_but_admin_can(
    client, now, user_headers, admin_headers, haircut
):
    booking_id = (await book(client, user_headers, haircut.id)).json()["id"]
    now.value = FIXED_NOW + timedelta(hours=22, minutes=30)  # до начала 1,5 часа

    late = await client.post(f"/bookings/{booking_id}/cancel", headers=user_headers)
    assert late.status_code == 409

    by_admin = await client.post(f"/bookings/{booking_id}/cancel", headers=admin_headers)
    assert by_admin.status_code == 200


async def test_foreign_booking_is_invisible(client, user_headers, other_user_headers, haircut):
    booking_id = (await book(client, user_headers, haircut.id)).json()["id"]
    resp = await client.post(f"/bookings/{booking_id}/cancel", headers=other_user_headers)
    assert resp.status_code == 404
    assert (await client.get("/bookings/me", headers=other_user_headers)).json() == []


async def test_admin_schedule(client, user_headers, admin_headers, haircut):
    await book(client, user_headers, haircut.id)
    await book(client, user_headers, haircut.id, "2030-01-09T12:00:00+03:00")

    assert (
        await client.get("/admin/schedule?date_from=2030-01-08", headers=user_headers)
    ).status_code == 403

    one_day = await client.get("/admin/schedule?date_from=2030-01-08", headers=admin_headers)
    two_days = await client.get(
        "/admin/schedule?date_from=2030-01-08&days=2", headers=admin_headers
    )
    assert len(one_day.json()) == 1
    assert len(two_days.json()) == 2


async def test_health_and_metrics(client, user_headers, haircut):
    assert (await client.get("/health")).json() == {"status": "ok"}
    await book(client, user_headers, haircut.id)
    metrics = (await client.get("/metrics")).text
    assert "booking_bookings_created_total" in metrics
    assert "http_request_duration_seconds" in metrics
