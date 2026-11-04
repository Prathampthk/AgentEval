"""Render measured process benchmark results; never synthesize missing metrics."""

import argparse
import json
import re
import statistics
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", default="reports/platform-benchmark.json")
parser.add_argument("--output", default="docs/PLATFORM_BENCHMARK_REPORT.md")
args = parser.parse_args()
data = json.loads(Path(args.input).read_text())
if not data.get("complete"):
    raise SystemExit("Refusing to present an incomplete experiment as complete")
rows = data["results"]
throughput = [r for r in rows if r["scenario"] == "throughput"]
assert len({r["workload_sha256"] for r in throughput}) == 1
lines = [
    "# Independent-process benchmark report",
    "",
    f"Source: `{args.input}`. Simulated provider; no response caching or billable tokens. "
    f"{data['jobs_per_throughput_variant']} jobs per throughput variant, {data['repetitions']} repetitions per worker level.",
    "",
    f"Python {data['python']}; {data['postgresql']}. Platform: {data['platform']}. "
    f"Logical CPUs: {data.get('logical_cpus')}; CPU quota: `{data.get('container_cpu_quota')}`; "
    f"memory limit bytes: `{data.get('container_memory_limit')}`. I/O timing: `{data['track_io_timing']}`.",
    "",
    "Each worker is an independent process with one active-evaluation slot and a two-connection pool. "
    "Startup and admission are excluded. P50/P95 completion latency includes waiting from the release barrier "
    "through result acknowledgment. Provider latency and claim-time distributions are retained separately in JSON.",
    "",
    "| Workers | Rep | Seconds | Jobs/s | P50 ms | P95 ms | Peak active | Retries | PG peak connections | PG peak lock waiters |",
    "|---|---|---|---|---|---|---|---|---|---|",
]
for r in throughput:
    p = r["postgres"]
    lines.append(
        f"| {r['worker_processes']} | {r['repetition']} | {r['duration_seconds']:.3f} | "
        f"{r['throughput_jobs_per_second']:.2f} | {r['completion_latency_ms']['p50']:.1f} | "
        f"{r['completion_latency_ms']['p95']:.1f} | {r['max_active_evaluations']} | "
        f"{r['retry_count']} | {p['sampled_peak_connections']} | {p['sampled_peak_lock_waiters']} |"
    )
lines += [
    "",
    "## Summary",
    "",
    "| Workers | Mean seconds | Sample SD seconds | Mean jobs/s | Ratio of mean times vs 1 |",
    "|---|---|---|---|---|",
]
base = statistics.mean(r["duration_seconds"] for r in throughput if r["worker_processes"] == 1)
for n in data["worker_levels"]:
    group = [r for r in throughput if r["worker_processes"] == n]
    times = [r["duration_seconds"] for r in group]
    mean = statistics.mean(times)
    sd = f"{statistics.stdev(times):.3f}" if len(times) > 1 else "NOT MEASURED (one repetition)"
    lines.append(
        f"| {n} | {mean:.3f} | {sd} | {statistics.mean(r['throughput_jobs_per_second'] for r in group):.2f} | {base / mean:.3f}× |"
    )
lines += [
    "",
    "## Crash recovery (separate probes)",
    "",
    "| Workers | Recovery seconds | Replaced processes | External effects for crashed job |",
    "|---|---|---|---|",
]
for r in rows:
    if r["scenario"] == "recovery":
        lines.append(
            f"| {r['worker_processes']} | {r['recovery_seconds']:.3f} | {r['replaced_processes']} | {r['external_effects_for_crashed_job']} |"
        )
lines += [
    "",
    "Recovery is post-response/pre-ack crash marker to accepted replacement result, using a two-second lease. "
    "Duplicate effects are expected and demonstrate why exactly-once external execution is not claimed.",
    "",
    "## PostgreSQL resource evidence",
    "",
    "| Workers | Rep | Commits | Rollbacks | Buffer hits | Blocks read | Temp bytes | Deadlocks | Container samples |",
    "|---|---|---|---|---|---|---|---|---|",
]
for r in throughput:
    p = r["postgres"]
    c = p["counter_deltas"]
    lines.append(
        f"| {r['worker_processes']} | {r['repetition']} | {c['xact_commit']} | {c['xact_rollback']} | "
        f"{c['blks_hit']} | {c['blks_read']} | {c['temp_bytes']} | {c['deadlocks']} | {len(p['container_samples'])} |"
    )
lines += [
    "",
    "| Workers | Rep | Sampled peak PostgreSQL CPU % | Sampled peak PostgreSQL memory MiB |",
    "|---|---|---|---|",
]
for r in throughput:
    samples = [s for s in r["postgres"]["container_samples"] if s and not s.get("unavailable")]
    cpu = [float(s["CPUPerc"].rstrip("%")) for s in samples if s.get("CPUPerc")]
    memory = []
    for sample in samples:
        match = re.match(r"([0-9.]+)(KiB|MiB|GiB|B)", sample.get("MemUsage", ""))
        if match:
            memory.append(
                float(match[1])
                * {"B": 1 / 1048576, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}[match[2]]
            )
    peak_cpu = f"{max(cpu):.2f}" if cpu else "NOT AVAILABLE"
    peak_memory = f"{max(memory):.2f}" if memory else "NOT AVAILABLE"
    lines.append(f"| {r['worker_processes']} | {r['repetition']} | {peak_cpu} | {peak_memory} |")
lines += [
    "",
    "Raw JSON retains sampled PostgreSQL container CPU%, memory and block I/O where available. "
    "These are coarse container-wide samples, not per-query CPU or isolated memory attribution. "
    "Database counter deltas include the measurement monitor; cumulative statistics can lag. Rollback counters include normal read-session rollback on close and are not failed-job counts. "
    "When track_io_timing is off, zero I/O time counters do not prove zero I/O cost.",
    "",
    "## Unexpected retries and diagnostic limits",
    "",
    "The first 16-process variant recorded 22 retries despite only eleven planned first-attempt provider failures. "
    "Its traces contain 1,010 completed evaluation executions for 1,000 accepted results, plus eleven failed generation attempts. "
    "This demonstrates repeated execution beyond the injected provider failures. Correlated PostgreSQL logs confirm ten statement timeouts on run-row SELECT FOR UPDATE acquisition; see `reports/platform-postgres-errors.json`. The full cause of the prolonged lock holds and every extra retry is NOT VERIFIED: "
    "the benchmark actor did not enable INFO-level worker event logging. No exhausted jobs or PostgreSQL deadlocks were recorded. "
    "All results were eventually accepted under the bounded retry policy, but this run is not a clean isolation of concurrency speedup. "
    "Retain it; investigate with event logging and query/lock profiling before production sizing. Other repetitions also show substantial shared-host variation.",
    "",
    "## Limits and reproducibility",
    "",
    "See [methodology](BENCHMARK_METHODOLOGY.md) and [deployment commands](DEPLOYMENT.md). "
    "Workloads have identical hashes, model settings and deterministic first-attempt failure selection; no cached responses are reused. "
    "Order rotates between repetitions. Shared-host scheduling, database history/cache warmth and monitor overhead remain confounders. "
    "Configured slots are not guaranteed observed overlap or a global production provider quota. "
    "These results do not predict live Gemini throughput, paid costs, HA or host-loss recovery.",
    "",
    "Preliminary attempts included a startup database connection timeout and an intentionally interrupted run to extend the measurement deadline. "
    "They were excluded as incomplete, not selected by performance. The complete experiment retains every planned configuration and repetition.",
    "",
]
Path(args.output).write_text("\n".join(lines))
print(f"Wrote {args.output} from completed measured evidence")
