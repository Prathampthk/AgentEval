# Simulated PostgreSQL benchmark report

Workload: 1000 jobs per configuration, 3 repetitions. All six variants completed; 6,000 accepted results total. Caching disabled. No live API calls.

| Repetition | Concurrency | Seconds | Jobs/s | Retries | Execution P95 ms | Completion P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 38.174 | 26.20 | 11 | 12.183 | 36451.324 |
| 1 | 16 | 13.286 | 75.26 | 11 | 17.688 | 12467.054 |
| 2 | 1 | 46.793 | 21.37 | 11 | 13.039 | 43403.367 |
| 2 | 16 | 12.827 | 77.96 | 11 | 19.318 | 11731.410 |
| 3 | 1 | 36.236 | 27.60 | 11 | 11.852 | 34609.952 |
| 3 | 16 | 13.096 | 76.36 | 11 | 18.182 | 12481.066 |

Mean sequential: **40.401 s** (sample SD 5.620 s). Mean concurrency 16: **13.070 s** (SD 0.231 s). Ratio of mean times: **3.091×**.

Each variant recorded 11 retries, zero exhausted jobs, and the configured active bound was respected. The provider injects a 5 ms minimum delay per operation and one transient failure every 97th case. This is a simulated workload through the actual PostgreSQL queue, not Gemini throughput. Higher concurrency can increase individual operation latency while improving total throughput. No caching advantage is included.

Environment: Python 3.12.14; PostgreSQL 17.11 (Debian 17.11-1.pgdg12+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14+deb12u1) 12.2.0, 64-bit; logical host CPUs reported 5; container CPU quota 4 CPUs; memory limit 32 GiB. Shared development infrastructure, no isolated-hardware claim.

Raw per-job records, all distributions, CPU times and cumulative RSS are in reports/benchmark.json. Token usage is unavailable, not zero; monetary cost is unmeasured. Peak RSS is cumulative across the benchmark process and retained reports. See BENCHMARK_METHODOLOGY.md for exact timing/quantile definitions.
