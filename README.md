# booking-api — REST API онлайн-записи

[![CI](https://github.com/tob1s3/booking-api/actions/workflows/ci.yml/badge.svg)](https://github.com/tob1s3/booking-api/actions/workflows/ci.yml)

Backend для записи клиентов к мастеру: услуги, свободное время, записи и отмены.
Логика та же, что в моём Telegram-боте для записи, но вынесена
в отдельный сервис. Теперь клиентом может быть Telegram-бот, сайт или мобильное приложение.

**Стек:** Python 3.12, FastAPI, PostgreSQL 16, SQLAlchemy 2 (async), Alembic, JWT, pytest,
Docker Compose, GitHub Actions, Prometheus-метрики.

## Что умеет

- Регистрация и вход по email и паролю. Пароли хранятся в виде хешей Argon2, доступ к API по JWT-токену.
- Каталог услуг. Создавать и менять услуги может только администратор.
- Свободное время с учётом рабочих часов, перерыва, выходных, длительности услуги и уже занятых записей.
- Запись и отмена. Клиент может отменить запись не позже, чем за N часов до начала, администратор — в любой момент.
- Расписание для администратора на день или неделю.
- `/health` для Docker и мониторинга, `/metrics` для Prometheus.
- Автоматическая документация: Swagger UI на `/docs`.

## Быстрый старт

```bash
git clone https://github.com/tob1s3/booking-api.git
cd booking-api
cp .env.example .env        # поменяйте POSTGRES_PASSWORD и JWT_SECRET
docker compose up -d --build
docker compose exec api python -m app.cli create-admin admin@example.com
```

Откройте http://localhost:8000/docs. Там можно авторизоваться кнопкой **Authorize** и
вызвать любой метод прямо из браузера.

### Пример через curl

```bash
# Вход администратора и создание услуги
TOKEN=$(curl -s -X POST localhost:8000/auth/token \
  -d "username=admin@example.com&password=<пароль>" | jq -r .access_token)
curl -X POST localhost:8000/services -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Стрижка", "duration_minutes": 60, "price": 1800}'

# Свободное время на день
curl "localhost:8000/services/1/slots?day=2026-11-20"

# Запись (время указывается с часовым поясом)
curl -X POST localhost:8000/bookings -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service_id": 1, "starts_at": "2026-11-20T10:00:00+03:00"}'
```

## API

| Метод | Путь | Доступ | Что делает |
|---|---|---|---|
| POST | `/auth/register` | все | регистрация |
| POST | `/auth/token` | все | вход, выдаёт JWT |
| GET | `/users/me` | клиент | профиль |
| GET | `/services` | все | активные услуги |
| POST | `/services` | админ | новая услуга |
| PATCH | `/services/{id}` | админ | изменить или выключить услугу |
| GET | `/services/{id}/slots?day=YYYY-MM-DD` | все | свободное время |
| POST | `/bookings` | клиент | записаться |
| GET | `/bookings/me` | клиент | мои записи |
| POST | `/bookings/{id}/cancel` | клиент / админ | отменить запись |
| GET | `/admin/schedule?date_from=…&days=…` | админ | расписание |
| GET | `/health`, `/metrics` | система | проверка живости и метрики |

## Как устроено

```
app/
├── main.py             сборка приложения, /health, /metrics
├── config.py           настройки из .env (pydantic-settings)
├── db.py               подключение к PostgreSQL, сессия на запрос
├── models.py           таблицы: users, services, bookings
├── schemas.py          схемы запросов и ответов (Pydantic)
├── security.py         пароли, JWT, проверка прав
├── slots.py            расчёт свободного времени — чистая функция без БД
├── booking_service.py  бизнес-логика записи и отмены
├── metrics.py          бизнес-метрики Prometheus
├── cli.py              создание администратора из консоли
└── routers/            HTTP-маршруты
alembic/                миграции базы данных
tests/                  31 тест: юнит-тесты слотов и API-тесты на настоящем PostgreSQL
```

## Ключевые решения

**Защита от двойной записи на уровне базы.** Если проверять «свободно ли время» только
в коде, два одновременных запроса могут оба увидеть свободный слот и оба записаться. Поэтому
в таблице `bookings` стоит EXCLUDE-ограничение PostgreSQL: две активные записи с
пересекающимися интервалами `tstzrange(starts_at, ends_at)` сохранить невозможно. Проверка
в коде остаётся для понятного сообщения об ошибке, а гарантию даёт база. Тест
`test_concurrent_requests_get_exactly_one_booking` отправляет 6 одновременных запросов
на одно время и проверяет, что успешен ровно один.

**Время хранится в UTC, расписание задаётся в часовом поясе заведения.** API принимает
время только с часовым поясом (`2026-11-20T10:00:00+03:00`). Время без пояса отклоняется,
потому что иначе непонятно, о каком часе речь.

**Расчёт слотов — чистая функция.** `slots.py` не знает про базу и HTTP, поэтому все
краевые случаи (перерыв, конец рабочего дня, соседние записи) проверяются быстрыми юнит-тестами.

**«Текущее время» — зависимость FastAPI.** В тестах часы можно заморозить или сдвинуть,
например чтобы проверить, что отменить запись за 1,5 часа до начала уже нельзя.

**Безопасность.** Пароли хешируются Argon2. Ответ на неверный пароль и на несуществующий
email одинаковый и занимает одинаковое время, чтобы нельзя было перебором узнать, какие
email зарегистрированы. Чужая запись возвращает 404, а не 403. Контейнер работает не от root.

**Миграции, а не `create_all`.** Схема меняется через Alembic. CI проверяет, что миграции
применяются, откатываются и совпадают с моделями (`alembic check`).

## Тесты и CI

```bash
pip install -r requirements-dev.txt
# нужен PostgreSQL; адрес тестовой базы:
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/booking_test
pytest
```

GitHub Actions на каждый push:
1. **Ruff** — стиль и типичные ошибки; **Bandit** — уязвимости в коде; **pip-audit** — известные уязвимости в зависимостях.
2. **Миграции и pytest** на PostgreSQL 16, поднятом как сервис.
3. **Сборка Docker-образа** и сканирование его **Trivy**.

## Мониторинг

`/metrics` отдаёт метрики HTTP (запросы, задержки, коды ответов) и бизнес-метрики:
`booking_bookings_created_total`, `booking_bookings_cancelled_total`, `booking_conflicts_total`.
Их собирает Prometheus из проекта [infra-monitoring](https://github.com/tob1s3/infra-monitoring).

## Что можно развить

- Несколько мастеров: добавить `staff_id` в EXCLUDE-ограничение (с расширением `btree_gist`).
- Refresh-токены и ограничение частоты запросов на `/auth/token`.
- Подключить booking-bot как клиента этого API.
