"""
Разовый bootstrap-скрипт для создания первого администратора.

Использование:
    python -m scripts.create_admin --username realadmin --email admin@example.com

Пароль запрашивается интерактивно.
"""
import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from db1.Database.database import async_factory
from db1.Security.security import Utils
from db1.models.Base1 import User


async def create_admin(username: str, email: str, password: str) -> None:
    async with async_factory() as db:
        existing_username = await db.execute(select(User).where(User.username == username))
        if existing_username.scalars().first():
            print(f"Ошибка: пользователь с username '{username}' уже существует.")
            sys.exit(1)

        existing_email = await db.execute(select(User).where(User.email == email))
        if existing_email.scalars().first():
            print(f"Ошибка: пользователь с email '{email}' уже существует.")
            sys.exit(1)

        admin = User(
            username=username,
            email=email,
            hashed_password=Utils.password_hash(password),
            role="admin",
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        print(f"Готово: администратор '{username}' (id={admin.id}) создан.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Создать первого администратора.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Пароль администратора: ")
    password_confirm = getpass.getpass("Повторите пароль: ")

    if password != password_confirm:
        print("Ошибка: пароли не совпадают.")
        sys.exit(1)
    if len(password) < 6:
        print("Ошибка: пароль должен быть не короче 6 символов.")
        sys.exit(1)

    asyncio.run(create_admin(args.username, args.email, password))


if __name__ == "__main__":
    main()