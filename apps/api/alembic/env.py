"""Alembic environment: usa la URL sincrona derivada de los settings de la app."""
from __future__ import annotations

from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool

from fitapp.config import settings
from fitapp.db import Base
from fitapp import models  # noqa: F401  (registra los modelos en Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Nombres de tablas gestionadas por esta app
_app_tables = set(target_metadata.tables.keys())


def include_object(obj: Any, name: str, type_: str, reflected: bool, compare_to: Any) -> bool:
    """Excluye tablas externas (PostGIS, Tiger geocoder, topology) del diff."""
    if type_ == "table" and reflected and name not in _app_tables:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
