"""Summarize opt-in process diagnostics, preserving raw evidence in gzip form."""

import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path

from agenteval.benchmark import distribution

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--archive", default="reports/lock-diagnostics.json.gz")
parser.add_argument("--output", default="reports/lock-diagnostics-summary.json")
args = parser.parse_args()
raw = Path(args.input).read_bytes()
data = json.loads(raw)
if not data.get("complete"):
    raise SystemExit("Incomplete experiment")
results = []
for row in data["results"]:
    diagnostics = row["diagnostics"]
    assert diagnostics["enabled"]
    sql = diagnostics["sql_operations"]
    run_locks = [s for s in sql if s["operation"] == "run_lock"]
    errors = collections.Counter(
        f"{s['operation']}:{s['sqlstate']}:{s['error_type']}" for s in sql if s["error_type"]
    )
    events = collections.Counter(e["event"] for e in diagnostics["worker_events"])
    blocked_samples = 0
    holder_states = collections.Counter()
    max_holder_age = 0
    root_holder_waits = collections.Counter()
    max_root_age = 0
    for sample in diagnostics["lock_samples"]:
        by_pid = {r["pid"]: r for r in sample["activity"]}
        blocked = [r for r in sample["activity"] if r["blockers"]]
        blocked_samples += bool(blocked)
        roots = {
            pid
            for waiter in blocked
            for pid in waiter["blockers"]
            if pid in by_pid and not by_pid[pid]["blockers"]
        }
        for pid in roots:
            holder = by_pid[pid]
            root_holder_waits[
                f"{holder['state']}:{holder['wait_event_type']}:{holder['wait_event']}"
            ] += 1
            max_root_age = max(max_root_age, holder["transaction_age_seconds"] or 0)
        for waiter in blocked:
            for pid in waiter["blockers"]:
                holder = by_pid.get(pid)
                if holder:
                    holder_states[holder["state"]] += 1
                    max_holder_age = max(max_holder_age, holder["transaction_age_seconds"] or 0)
    results.append(
        dict(
            worker_processes=row["worker_processes"],
            repetition=row["repetition"],
            jobs_completed=row["jobs_completed"],
            duration_seconds=row["duration_seconds"],
            retry_count=row["retry_count"],
            max_active_evaluations=row["max_active_evaluations"],
            workload_sha256=row["workload_sha256"],
            sql_errors=dict(errors),
            worker_events=dict(events),
            run_lock_latency_ms=distribution([(s["end"] - s["start"]) * 1000 for s in run_locks]),
            worker_event_loop_delay_ms=distribution(
                [s["delay_seconds"] * 1000 for s in diagnostics.get("event_loop_samples", [])]
            ),
            run_lock_to_transaction_end_start_ms=distribution(
                [
                    (s["transaction_end_started"] - s["lock_returned"]) * 1000
                    for s in diagnostics.get("run_lock_transactions", [])
                ]
            ),
            run_lock_max_ms=max(((s["end"] - s["start"]) * 1000 for s in run_locks), default=None),
            max_sampled_root_blocker_transaction_age_seconds=max_root_age,
            sampled_root_blocker_waits=dict(root_holder_waits),
            max_sampled_blocker_transaction_age_seconds=max_holder_age,
            samples_with_blockers=blocked_samples,
            sampled_blocker_states=dict(holder_states),
        )
    )
summary = dict(
    kind="instrumented-lock-reproduction",
    complete=True,
    raw_sha256=hashlib.sha256(raw).hexdigest(),
    archive=args.archive,
    jobs_per_variant=data["jobs_per_throughput_variant"],
    repetitions=data["repetitions"],
    source_sha256=data["source_sha256"],
    results=results,
    limitations=[
        "Diagnostic tracing changes timing; do not replace original performance report.",
        "Sampled transaction age is not exact lock holding time; short waits can be missed.",
        "No timeout reproduction does not prove the historical cause resolved.",
    ],
)
with open(args.archive, "wb") as file:
    file.write(gzip.compress(raw, mtime=0))
Path(args.output).write_text(json.dumps(summary, indent=2) + "\n")
for row in results:
    print(
        "workers",
        row["worker_processes"],
        "rep",
        row["repetition"],
        "retries",
        row["retry_count"],
        "run-lock P99 ms",
        round(row["run_lock_latency_ms"]["p99"], 2),
        "SQL errors",
        row["sql_errors"],
    )
