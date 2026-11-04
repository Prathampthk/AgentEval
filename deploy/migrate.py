"""One-shot schema administration; runtime services never receive this URL."""

import asyncio
import os
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def grants():
    engine = create_async_engine(
        os.environ["AGENTEVAL_MIGRATION_DATABASE_URL"], hide_parameters=True
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(text("GRANT USAGE ON SCHEMA public TO agenteval_runtime"))
            await connection.execute(
                text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO agenteval_runtime")
            )
            await connection.execute(
                text(
                    "GRANT INSERT ON datasets, test_cases, evaluation_runs, evaluation_jobs, evaluation_results, documents, document_chunks TO agenteval_runtime"
                )
            )
            await connection.execute(
                text("GRANT UPDATE ON evaluation_runs, evaluation_jobs TO agenteval_runtime")
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    asyncio.run(grants())
