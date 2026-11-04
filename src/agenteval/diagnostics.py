"""Opt-in benchmark diagnostics: numeric lock graphs and SQL categories, no payloads."""

import json
import logging
import os
from time import perf_counter

from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError


def sql_category(statement):
    query = (statement or "").lstrip().upper()
    if query.startswith("SELECT") and "FOR UPDATE" in query:
        # Claims join runs but lock only jobs. Classify the locked/projection
        # relation rather than any table mentioned by a join or subquery.
        if query.startswith("SELECT EVALUATION_JOBS.") or "FOR UPDATE OF EVALUATION_JOBS" in query:
            return "job_lock_or_claim"
        if query.startswith("SELECT EVALUATION_RUNS."):
            return "run_lock"
    for verb in ("SELECT", "UPDATE", "INSERT", "DELETE", "COMMIT", "ROLLBACK"):
        if query.startswith(verb):
            return verb.lower()
    return "other"


class WorkerTrace(logging.Handler):
    def __init__(self, trace):
        super().__init__()
        self.trace = trace

    def emit(self, record):
        # This handler is attached only to AgentEval's structured worker logger.
        payload = json.loads(record.getMessage())
        allowed = {
            "event",
            "job_id",
            "run_id",
            "attempt",
            "worker_id",
            "error_type",
            "category",
            "count",
            "retry_delay_seconds",
            "concurrency",
            "concurrency_scope",
            "max_active_evaluations",
            "active_evaluations",
            "attempts_started",
            "pending_loops",
        }
        safe = {key: value for key, value in payload.items() if key in allowed}
        self.trace.write(
            json.dumps(
                dict(kind="worker-event", time=perf_counter(), process_id=os.getpid(), **safe)
            )
            + "\n"
        )


def instrument_sql(database, trace):
    """Instrument only this engine; timing includes lock waits, never bind values."""
    engine = database.engine.sync_engine

    @event.listens_for(engine, "before_cursor_execute")
    def before(conn, cursor, statement, parameters, context, executemany):
        context.diagnostic_started = perf_counter()

    def write(conn, statement, context, error=None):
        started = getattr(context, "diagnostic_started", None)
        if started is None:
            return
        try:
            backend_pid = conn.connection.driver_connection.get_server_pid()
        except (AttributeError, TypeError, SQLAlchemyError):
            backend_pid = None
        trace.write(
            json.dumps(
                dict(
                    kind="sql-operation",
                    process_id=os.getpid(),
                    backend_pid=backend_pid,
                    operation=sql_category(statement),
                    start=started,
                    end=perf_counter(),
                    error_type=type(error).__name__ if error else None,
                    sqlstate=getattr(error, "sqlstate", None),
                )
            )
            + "\n"
        )

    @event.listens_for(engine, "after_cursor_execute")
    def after(conn, cursor, statement, parameters, context, executemany):
        write(conn, statement, context)

    @event.listens_for(engine, "handle_error")
    def failed(exception_context):
        write(
            exception_context.connection,
            exception_context.statement,
            exception_context.execution_context,
            exception_context.original_exception,
        )


async def lock_snapshot(database):
    """No query text, parameters, arbitrary application names or credentials leave PG."""
    async with database.sessions() as session:
        rows = (
            (
                await session.execute(
                    text("""
            SELECT pid, state, wait_event_type, wait_event,
                   extract(epoch FROM clock_timestamp()-xact_start)::float AS transaction_age_seconds,
                   extract(epoch FROM clock_timestamp()-query_start)::float AS query_age_seconds,
                   pg_blocking_pids(pid) AS blockers
            FROM pg_stat_activity
            WHERE datname=current_database() AND pid<>pg_backend_pid()
              AND (xact_start IS NOT NULL OR cardinality(pg_blocking_pids(pid))>0)
        """)
                )
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]
