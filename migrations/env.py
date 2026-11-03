"""Use the configured async PostgreSQL connection; do not log its URL."""

import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from agenteval.models import Base

config = context.config


def run_sync(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    url = os.environ.get("AGENTEVAL_MIGRATION_DATABASE_URL") or os.environ.get(
        "AGENTEVAL_DATABASE_URL"
    )
    if not url:
        raise RuntimeError("AGENTEVAL_DATABASE_URL is required for migrations")
    engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_sync)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url="postgresql+asyncpg://",
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
