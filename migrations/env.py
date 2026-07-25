import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
# Импортируем твой Base, чтобы autogenerate видел модели
from db1.models.Base1 import Base

# Это объект конфигурации Alembic
config = context.config

# Настройка логов
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные моделей для поддержки autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' моде."""
    # Пытаемся взять URL из окружения (Docker), если нет — из alembic.ini
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в 'online' моде."""

    # Получаем стандартную секцию настроек из alembic.ini
    alembic_config = config.get_section(config.config_ini_section, {})

    # ГЛАВНОЕ ИСПРАВЛЕНИЕ: 
    # Если мы в Docker, берем URL из переменной окружения DATABASE_URL
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # Заменяем asyncpg на обычный драйвер только для миграций
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        alembic_config["sqlalchemy.url"] = db_url

    connectable = engine_from_config(
        alembic_config,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()