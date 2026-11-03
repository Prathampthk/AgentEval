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
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE evaluation_results, evaluation_jobs, evaluation_runs, test_cases, datasets CASCADE"
            )
        )
    try:
        yield database
    finally:
        await database.close()
