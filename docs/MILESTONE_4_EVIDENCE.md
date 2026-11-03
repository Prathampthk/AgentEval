# Milestone 4 evidence — bounded execution

Validated 2026-11-03 on the current cloud instance using Python 3.12.14, real PostgreSQL 17 and controlled fake-provider workloads. This is correctness evidence, not a throughput benchmark.

| Check | Observed outcome |
|---|---|
| Full pytest suite | **84 passed**, zero failures/errors/skips; 50 unit/provider/configuration tests and 34 PostgreSQL integration tests |
| Actual evaluation overlap | An independently instrumented evaluation wrapper observed 16 active evaluations at the barrier |
| Configured bound | Peak active evaluations stayed at or below 16 while all 120 jobs completed |
| Queue backpressure/no prefetch | At the barrier, exactly 16 jobs were RUNNING and 104 remained PENDING |
| Task growth | Managed named tasks stayed within `4 * concurrency + 1` at the barrier; total tasks stayed within the test's baseline plus `4 * concurrency + 6`; no worker-owned tasks remained after shutdown |
| Failure and timeout isolation | Two failed jobs did not prevent six other jobs in their run from completing; active counters returned to zero |
| Cancellation releases capacity | A canceled blocked evaluation released the sole lane, which then completed another run |
| Graceful shutdown | Two active jobs finished, three unclaimed jobs stayed PENDING with attempts zero; replacement worker completed them |
| Drain timeout | Both active provider tasks were canceled, leases and pending results were retained; expiration/recovery and replacement execution completed the jobs |
| Shutdown during claim | Committed claim was retained for recovery, with no provider evaluation started |
| Public worker entry point | `AGENTEVAL_WORKER_CONCURRENCY=16` startup logged process-local concurrency 16; local HTTP queue smoke passed |
| Lint and formatting | Passed |

Test source: `tests/integration/test_worker_pool.py` and `tests/test_worker_config.py`. Current-run report: ignored `artifacts/tests.xml`; focused-run report: `artifacts/pool-tests.xml` (the full report is authoritative after the final test addition).

The 120-job controlled test uses six submissions of a 20-case dataset. A barrier, not a latency assumption, holds the first 16 real evaluation calls open before releasing the workload. It measures neither 1,000-job throughput nor live Gemini capacity. No speedup, P95 latency, token-cost or caching result is claimed.

The initial focused run had a pytest collection filename collision; renaming the unit module resolved it. All tests in the final suite executed successfully. A pre-existing Starlette test-client deprecation warning remains.

Remaining limits: concurrency is process-local; API synchronous routes have separate capacity; database outages and production shutdown/network partitions need further reliability validation. No overall run deadline, Retry-After support, global provider limit, live Gemini test or performance benchmark is included.
