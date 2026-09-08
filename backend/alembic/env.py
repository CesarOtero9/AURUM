from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from aurum.infrastructure.persistence_models import Base

config = context.config
configured_url = config.get_main_option("sqlalchemy.url")
database_url = configured_url or os.environ.get("AURUM_DATABASE_URL")
if not database_url:
    raise RuntimeError("AURUM_DATABASE_URL must be configured for Alembic")
config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section) or {}, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
