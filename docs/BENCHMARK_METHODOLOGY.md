# Benchmark methodology

Use a dedicated AGENTEVAL_BENCHMARK_DATABASE_URL ending in `_benchmark`; the local database helper creates one separately from development and test databases. No existing data is truncated. The runner refuses to start when unfinished benchmark jobs exist. It always uses its own simulated provider, regardless of GEMINI settings.

Command:

```
.venv/bin/python scripts/local_db.py start
.venv/bin/python scripts/local_db.py admin .venv/bin/python -m agenteval.benchmark --jobs 1000 --repetitions 3 --output reports/benchmark.json
```

Each repetition submits the same 1,000 logical cases (50 datasets/runs of 20 cases) and compares one worker process at concurrency 1 against one at concurrency 16. Every generation and judge operation waits at least 5 ms by default. Every 97th case receives one controlled transient rate-limit failure; attempts and backoff use the real persistent queue. This is a repeatable controlled workload, not an emulation of Gemini latency/rate limits.

Preparation/admission is excluded from timed worker completion. Queue wait is measured from the start of the timed, fully admitted workload to each first claim. Completion latency is start-to-accepted-result; execution latency is generation plus judgment; provider-operation latency includes failed attempts and event-loop scheduling. These are distinct quantities. Quantiles use the nearest-rank definition; 1,000 samples support P50/P95/P99 descriptive reporting, without confidence guarantees.

Speedup is mean sequential completion time divided by mean concurrent completion time across all repetitions. All repetitions and standard deviations are retained; no best-run selection. Throughput is jobs divided by timed completion. Raw per-job records accompany summary distributions. Retries, error rate, observed maximum active evaluations, CPU time and cumulative process peak RSS are recorded. RSS includes retained reports and is not an isolated per-configuration memory comparison.

The report records Python/PostgreSQL/platform and logical CPUs. Container quota/memory limits are recorded with final report metadata when available. The environment is shared development infrastructure, not a dedicated performance lab. UUID tie ordering and scheduling can vary; seed fixes retry jitter draws, not all OS/database scheduling.

Caching is disabled. Cache hit rate is not applicable. The simulated provider supplies no billable token metadata; token usage and monetary costs remain null/unmeasured. Live Gemini benchmarks must be separate, explicitly budgeted experiments and cannot inherit this throughput claim.
