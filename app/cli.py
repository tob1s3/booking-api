"""Команды для администрирования из консоли.

    python -m app.cli create-admin admin@example.com "Имя"

Пароль спрашивается интерактивно (или берётся из переменной ADMIN_PASSWORD),
чтобы он не остался в истории командной строки.
"""

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.security import hash_password


async def create_admin(email: str, name: str, password: str) -> None:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            user = User(email=email.lower(), name=name, password_hash=hash_password(password))
            session.add(user)
        user.is_admin = True
        await session.commit()
        print(f"Администратор {user.email} готов")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="создать администратора или выдать права")
    admin.add_argument("email")
    admin.add_argument("name", nargs="?", default="Администратор")
    args = parser.parse_args()

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Пароль: ")
    if len(password) < 8:
        sys.exit("Пароль должен быть не короче 8 символов")
    asyncio.run(create_admin(args.email, args.name, password))


if __name__ == "__main__":
    main()
