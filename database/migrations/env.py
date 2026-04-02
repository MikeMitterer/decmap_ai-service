import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object — access to .ini file values
config = context.config

# Override sqlalchemy.url from environment variable if present
postgres_url = os.environ.get("POSTGRES_URL")
if postgres_url:
    # Alembic uses sqlalchemy URLs — psycopg3 async driver prefix unsupported here;
    # use synchronous psycopg2-compatible URL for Alembic schema operations.
    if postgres_url.startswith("postgresql://"):
        config.set_main_option("sqlalchemy.url", postgres_url)
    elif postgres_url.startswith("postgresql+psycopg://"):
        sync_url = postgres_url.replace("postgresql+psycopg://", "postgresql://")
        config.set_main_option("sqlalchemy.url", sync_url)

# Interpret alembic.ini logging config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No MetaData object — we use raw SQL in migrations
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection required)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
