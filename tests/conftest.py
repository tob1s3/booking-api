"""Общие фикстуры. Тесты идут на настоящем PostgreSQL: без него не проверить
EXCLUDE-ограничение, на котором держится защита от двойной записи."""

import os
from datetime import UTC, datetime

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/booking_test",
)
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.deps import get_now  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Service, User  # noqa: E402
from app.security import hash_password  # noqa: E402

# Понедельник, 7 января 2030 года, 10:00 по Москве. Часы в тестах заморожены.
FIXED_NOW = datetime(2030, 1, 7, 7, 0, tzinfo=UTC)
PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session", autouse=True)
async def database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables():
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE bookings, services, users RESTART IDENTITY CASCADE"))


@pytest.fixture
def now():
    """Позволяет тесту сдвинуть «текущее время»: now.value = ..."""

    class Clock:
        value = FIXED_NOW

    clock = Clock()
    app.dependency_overrides[get_now] = lambda: clock.value
    yield clock
    app.dependency_overrides.pop(get_now, None)


@pytest.fixture
async def client(now):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _create_user(email: str, is_admin: bool = False) -> None:
    async with SessionLocal() as session:
        session.add(
            User(
                email=email,
                name=email.split("@")[0],
                password_hash=hash_password(PASSWORD),
                is_admin=is_admin,
            )
        )
        await session.commit()


async def _token(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/auth/token", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def user_headers(client):
    await _create_user("client@example.com")
    return await _token(client, "client@example.com")


@pytest.fixture
async def other_user_headers(client):
    await _create_user("other@example.com")
    return await _token(client, "other@example.com")


@pytest.fixture
async def admin_headers(client):
    await _create_user("admin@example.com", is_admin=True)
    return await _token(client, "admin@example.com")


@pytest.fixture
async def haircut():
    """Услуга на 60 минут."""
    async with SessionLocal() as session:
        service = Service(title="Стрижка", duration_minutes=60, price=1800)
        session.add(service)
        await session.commit()
        return service
