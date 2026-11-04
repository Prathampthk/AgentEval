# Independent-process benchmark report

Source: `reports/platform-benchmark.json`. Simulated provider; no response caching or billable tokens. 1000 jobs per throughput variant, 3 repetitions per worker level.

Python 3.12.14; PostgreSQL 17.11 (Debian 17.11-1.pgdg12+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14+deb12u1) 12.2.0, 64-bit. Platform: Linux-6.18.57-x86_64-with-glibc2.41. Logical CPUs: 5; CPU quota: `400000 100000`; memory limit bytes: `34359738368`. I/O timing: `off`.

Each worker is an independent process with one active-evaluation slot and a two-connection pool. Startup and admission are excluded. P50/P95 completion latency includes waiting from the release barrier through result acknowledgment. Provider latency and claim-time distributions are retained separately in JSON.

| Workers | Rep | Seconds | Jobs/s | P50 ms | P95 ms | Peak active | Retries | PG peak connections | PG peak lock waiters |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 39.901 | 25.06 | 18546.8 | 37122.3 | 1 | 11 | 4 | 0 |
| 4 | 1 | 13.942 | 71.72 | 6954.4 | 12780.9 | 4 | 11 | 10 | 1 |
| 8 | 1 | 12.668 | 78.94 | 6656.0 | 11786.3 | 4 | 11 | 18 | 6 |
| 16 | 1 | 71.762 | 13.93 | 6450.8 | 34053.1 | 5 | 22 | 34 | 16 |
| 4 | 2 | 12.691 | 78.80 | 6154.1 | 11623.5 | 4 | 11 | 10 | 2 |
| 8 | 2 | 13.593 | 73.57 | 7042.7 | 12751.3 | 4 | 11 | 19 | 6 |
| 16 | 2 | 16.800 | 59.52 | 9468.1 | 16016.1 | 5 | 11 | 34 | 11 |
| 1 | 2 | 46.336 | 21.58 | 26828.5 | 44550.5 | 1 | 11 | 5 | 0 |
| 8 | 3 | 14.449 | 69.21 | 7643.1 | 13584.1 | 5 | 11 | 18 | 5 |
| 16 | 3 | 25.332 | 39.48 | 12344.9 | 23641.7 | 6 | 11 | 34 | 13 |
| 1 | 3 | 77.897 | 12.84 | 21641.5 | 75885.0 | 1 | 11 | 5 | 0 |
| 4 | 3 | 15.000 | 66.67 | 6949.4 | 13902.3 | 4 | 11 | 10 | 2 |

## Summary

| Workers | Mean seconds | Sample SD seconds | Mean jobs/s | Ratio of mean times vs 1 |
|---|---|---|---|---|
| 1 | 54.712 | 20.335 | 19.83 | 1.000× |
| 4 | 13.878 | 1.156 | 72.40 | 3.942× |
| 8 | 13.570 | 0.891 | 73.91 | 4.032× |
| 16 | 37.965 | 29.578 | 37.64 | 1.441× |

## Crash recovery (separate probes)

| Workers | Recovery seconds | Replaced processes | External effects for crashed job |
|---|---|---|---|
| 1 | 2.106 | 1 | 2 |
| 4 | 2.110 | 1 | 2 |
| 8 | 2.042 | 1 | 2 |
| 16 | 2.071 | 1 | 2 |

Recovery is post-response/pre-ack crash marker to accepted replacement result, using a two-second lease. Duplicate effects are expected and demonstrate why exactly-once external execution is not claimed.

## PostgreSQL resource evidence

| Workers | Rep | Commits | Rollbacks | Buffer hits | Blocks read | Temp bytes | Deadlocks | Container samples |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 2058 | 4910 | 502588 | 0 | 0 | 0 | 15 |
| 4 | 1 | 2044 | 4440 | 435655 | 0 | 0 | 0 | 5 |
| 8 | 1 | 2094 | 5954 | 571867 | 0 | 0 | 0 | 5 |
| 16 | 1 | 7255 | 33587 | 1696121 | 0 | 0 | 0 | 20 |
| 4 | 2 | 2082 | 4326 | 261119 | 0 | 0 | 0 | 5 |
| 8 | 2 | 2082 | 6089 | 466399 | 0 | 0 | 0 | 5 |
| 16 | 2 | 2099 | 9537 | 823343 | 0 | 0 | 0 | 6 |
| 1 | 2 | 2038 | 4997 | 614860 | 0 | 0 | 0 | 17 |
| 8 | 3 | 2067 | 6259 | 548910 | 0 | 0 | 0 | 6 |
| 16 | 3 | 2131 | 11846 | 861287 | 0 | 0 | 0 | 9 |
| 1 | 3 | 2043 | 5264 | 688914 | 0 | 0 | 0 | 20 |
| 4 | 3 | 2051 | 4581 | 494875 | 0 | 0 | 0 | 6 |

| Workers | Rep | Sampled peak PostgreSQL CPU % | Sampled peak PostgreSQL memory MiB |
|---|---|---|---|
| 1 | 1 | 32.51 | 115.90 |
| 4 | 1 | 62.19 | 136.70 |
| 8 | 1 | 76.69 | 163.10 |
| 16 | 1 | 103.50 | 211.50 |
| 4 | 2 | 52.70 | 139.90 |
| 8 | 2 | 107.58 | 165.20 |
| 16 | 2 | 183.29 | 216.20 |
| 1 | 2 | 36.91 | 126.10 |
| 8 | 3 | 95.53 | 170.50 |
| 16 | 3 | 221.34 | 220.10 |
| 1 | 3 | 84.01 | 129.10 |
| 4 | 3 | 68.62 | 148.70 |

Raw JSON retains sampled PostgreSQL container CPU%, memory and block I/O where available. These are coarse container-wide samples, not per-query CPU or isolated memory attribution. Database counter deltas include the measurement monitor; cumulative statistics can lag. Rollback counters include normal read-session rollback on close and are not failed-job counts. When track_io_timing is off, zero I/O time counters do not prove zero I/O cost.

## Unexpected retries and diagnostic limits

The first 16-process variant recorded 22 retries despite only eleven planned first-attempt provider failures. Its traces contain 1,010 completed evaluation executions for 1,000 accepted results, plus eleven failed generation attempts. This demonstrates repeated execution beyond the injected provider failures. Correlated PostgreSQL logs confirm ten statement timeouts on run-row SELECT FOR UPDATE acquisition; see `reports/platform-postgres-errors.json`. The full cause of the prolonged lock holds and every extra retry is NOT VERIFIED: the benchmark actor did not enable INFO-level worker event logging. No exhausted jobs or PostgreSQL deadlocks were recorded. All results were eventually accepted under the bounded retry policy, but this run is not a clean isolation of concurrency speedup. Retain it; investigate with event logging and query/lock profiling before production sizing. Other repetitions also show substantial shared-host variation.

## Limits and reproducibility

See [methodology](BENCHMARK_METHODOLOGY.md) and [deployment commands](DEPLOYMENT.md). Workloads have identical hashes, model settings and deterministic first-attempt failure selection; no cached responses are reused. Order rotates between repetitions. Shared-host scheduling, database history/cache warmth and monitor overhead remain confounders. Configured slots are not guaranteed observed overlap or a global production provider quota. These results do not predict live Gemini throughput, paid costs, HA or host-loss recovery.

Preliminary attempts included a startup database connection timeout and an intentionally interrupted run to extend the measurement deadline. They were excluded as incomplete, not selected by performance. The complete experiment retains every planned configuration and repetition.
