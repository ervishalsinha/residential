from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_database_url() -> str:
    direct = os.getenv("DATABASE_URL")
    if direct:
        return direct

    settings_url = get_settings().database_url
    if settings_url:
        return settings_url

    raise Exception("DATABASE_URL not set")


def run_migrations_offline() -> None:
    database_url = _resolve_database_url()

    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        compare_type=True,
        literal_binds=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database_url = _resolve_database_url()

    connectable = create_engine(database_url, pool_pre_ping=True)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
