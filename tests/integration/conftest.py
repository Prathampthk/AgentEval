import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url

from agenteval.database import Database


@pytest.fixture(scope="session")
def pg_url():
    url = os.getenv("AGENTEVAL_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated PostgreSQL test database is not configured")
    parsed = make_url(url)
    if parsed.drivername != "postgresql+asyncpg" or not parsed.database.endswith("_test"):
        pytest.fail("Integration tests require a dedicated PostgreSQL database ending in _test")
    # Explicitly target only the test database, including the migration connection.
    old = {
        key: os.environ.get(key)
        for key in ("AGENTEVAL_DATABASE_URL", "AGENTEVAL_MIGRATION_DATABASE_URL")
    }
    try:
        for key in old:
            os.environ[key] = url
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return url


@pytest.fixture
async def db(pg_url):
    database = Database(pg_url)
    try:
        # Retry only infrastructure connection acquisition before the test starts.
        # Once connected, test transactions and operations are never retried here.
        async with asyncio.timeout(30):
            while True:
                try:
                    connection = await database.engine.connect()
                except (TimeoutError, OSError):
                    await asyncio.sleep(0.1)
                else:
                    break
        try:
            async with connection.begin():
                await connection.execute(
                    text(
                        "TRUNCATE document_chunks, documents, evaluation_results, evaluation_jobs, evaluation_runs, test_cases, datasets CASCADE"
                    )
                )
        finally:
            await connection.close()
        yield database
    finally:
        await database.close()
