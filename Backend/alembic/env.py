"""
Alembic environment script.

Deliberately does NOT read sqlalchemy.url from alembic.ini. Instead it
reuses the exact same Settings the app itself uses (app/config.py), so
migrations always target whatever DB the app is currently configured for -
one source of truth for DB credentials, no drift between .env and
alembic.ini, and `CENTRY_USE_SQLITE=true alembic upgrade head` works for
local testing without touching alembic.ini at all.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make sure `app` is importable when alembic is run from the project root
# (it is, by default, since alembic.ini's script_location is relative to cwd).
from app.config import settings
from app.database import Base

# Import every module that defines models so they register on Base.metadata
# before we hand that metadata to Alembic for autogenerate comparisons.
# Add new model modules here as they're created.
from app.models import models  # noqa: F401

# Alembic Config object, gives access to values within alembic.ini.
config = context.config

# Inject the app's real DB URL (built from CENTRY_* env vars / .env) into
# alembic's config in-memory, instead of hardcoding it in alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up loggers per alembic.ini's [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata autogenerate compares the DB against - this is what makes
# `alembic revision --autogenerate` pick up new/changed models automatically.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emits SQL to stdout).

    Useful for generating a .sql script to hand to a DBA, or for
    autogenerate in environments where the DB isn't directly reachable but
    the URL is still known - not our main path (we run online), but kept
    since it's a standard, harmless part of the alembic template.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live DB connection - the normal path."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # catch column type changes, not just add/drop
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
