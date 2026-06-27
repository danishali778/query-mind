"""Alembic environment for query-mind app database migrations."""

from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.orm_models import *  # noqa: F401,F403,E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def _is_auth_foreign_key(obj) -> bool:
    """Return True for reflected foreign keys pointing at Supabase Auth tables."""
    elements = getattr(obj, "elements", [])
    for element in elements:
        target_column = getattr(element, "column", None)
        target_table = getattr(target_column, "table", None)
        if getattr(target_table, "schema", None) == "auth":
            return True
    return False


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Filter objects that Alembic autogenerate should not manage.

    Supabase Auth owns the `auth` schema. The live app tables have foreign keys
    into `auth.users`, but runtime ORM metadata intentionally avoids modeling
    that schema so SQLite repository tests stay portable.
    """
    if type_ == "foreign_key_constraint" and reflected and compare_to is None:
        if _is_auth_foreign_key(obj):
            return False
    return True


def _database_url() -> str:
    if not settings.app_database_url:
        raise RuntimeError(
            "APP_DATABASE_URL is required to run Alembic migrations for the app database."
        )
    return settings.app_database_url


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
