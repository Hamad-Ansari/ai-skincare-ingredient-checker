"""Alembic environment configured from application settings."""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import models as _models  # noqa: E402, F401
from backend.app.core.config import get_settings  # noqa: E402
from backend.app.database.base import Base  # noqa: E402
from backend.app.database.session import create_database_engine  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

settings = get_settings()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a DBAPI connection."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=make_url(settings.database_url).get_backend_name() == "sqlite",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using the application-configured database engine."""
    engine = create_database_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                render_as_batch=make_url(settings.database_url).get_backend_name() == "sqlite",
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
