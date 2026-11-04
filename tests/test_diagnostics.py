import io
import json
import logging

from agenteval.diagnostics import WorkerTrace, sql_category


def test_diagnostic_categories_never_return_query_or_parameters():
    assert sql_category("SELECT evaluation_runs.id FROM evaluation_runs FOR UPDATE") == "run_lock"
    assert (
        sql_category("SELECT evaluation_jobs.id FROM evaluation_jobs FOR UPDATE SKIP LOCKED")
        == "job_lock_or_claim"
    )
    assert sql_category("SELECT 'private patient information'") == "select"
    assert sql_category(None) == "other"
    assert (
        sql_category(
            "SELECT evaluation_jobs.id FROM evaluation_jobs JOIN evaluation_runs ON true FOR UPDATE OF evaluation_jobs SKIP LOCKED"
        )
        == "job_lock_or_claim"
    )


def test_worker_trace_discards_unknown_payload_fields():
    trace = io.StringIO()
    handler = WorkerTrace(trace)
    record = logging.LogRecord(
        "agenteval.worker",
        logging.INFO,
        "",
        0,
        json.dumps({"event": "job_claimed", "job_id": "id", "secret": "never persist"}),
        (),
        None,
    )
    handler.emit(record)
    event = json.loads(trace.getvalue())
    assert event["kind"] == "worker-event" and event["job_id"] == "id"
    assert "secret" not in event and "never persist" not in trace.getvalue()
