# Durable job execution — milestone 4

Implemented by `jobs.py`, `worker.py`, and migration `0002`. A fixed pool processes 1–16 evaluations per process, configured by AGENTEVAL_WORKER_CONCURRENCY (default 1). A real PostgreSQL test proves overlap, the active bound and bounded task growth. No new schema migration is required for milestone 4.

## Submission and admission

`POST /queued-runs` requires an opaque `Idempotency-Key` header (1–200 nonblank characters) and returns HTTP 202. Scope is the entire local installation/database. Equivalent submissions return the original run even after it finishes or the queue fills. Reusing a key with a different dataset, prompt, provider/model/rubric or execution policy returns 409. There is no TTL or key eviction yet; deleting history manually also removes its deduplication protection.

A PostgreSQL unique constraint protects keys. Submission, payload hash and all case jobs commit together. An installation-wide transaction-scoped advisory lock serializes admissions and duplicate resolution. Active PENDING/RUNNING jobs are counted under that lock; the default cap is 1,000 jobs. Concurrent draining only makes this count conservative. Other submission paths must use the same lock to preserve this bound. Queue overload returns 429 without creating a partial run. This limit is job count, not provider request concurrency.

## Claiming and state transitions

Legal job transitions:

- PENDING → RUNNING or CANCELED.
- RUNNING → COMPLETED, FAILED, PENDING (retry/recovery), or CANCELED.
- Terminal states do not reactivate through queue operations.

Claims use a short `FOR UPDATE OF evaluation_jobs SKIP LOCKED` transaction. Each claim increments the persisted attempt count, sets a new random fencing token and owner, and commits before any provider call. Workers select only jobs matching their provider name, model and simulation flag. Run status RUNNING means accepted and not yet terminal, even if all jobs are still PENDING; inspect job states for actual progress.

## Leases, retries and finalization

Default lease: 60 seconds. Heartbeat interval: 15 seconds. Renewal and result writes require RUNNING status, matching owner/token and an unexpired lease, using the database clock. Renewal never revives an expired lease. Completion updates the guarded job, inserts one result, and updates the run aggregate in one transaction. Unique and composite foreign-key constraints bind one result to the correct job, run, case and dataset.

Run-level row locks serialize aggregate changes; result finalization, failure, recovery and cancellation take the run lock before job locks. Claiming/renewal never wait for a run row lock, avoiding inverted lock order. Provider calls retain neither transaction nor connection.

Retryable provider failures use full-jitter capped exponential backoff: delay uniformly between 0 and `min(60, 2 ** (attempt - 1))` seconds. Default maximum is three attempts. Attempts and next eligible time persist across restarts. Permanent errors fail immediately. Provider Retry-After handling is not implemented yet. A retry attempt repeats the whole generation/judgment evaluation; a successful generation followed by judge failure can incur repeated generation charges.

The worker scans up to 100 expired leases per iteration. Expired jobs return to PENDING when budget remains; otherwise they become FAILED with `lease_expired`. Old workers cannot renew or save over a later claim. A worker crash after receiving a response can repeat an external call: execution is at-least-once attempts, with fenced result persistence, **not exactly-once provider execution**. Finite attempt budgets can end in failure.

Successful case results remain visible when other cases fail or the run is canceled. Once every job is terminal, any failed job makes the run FAILED; otherwise canceled jobs make it CANCELED; otherwise it is COMPLETED. These are execution outcomes, not answer quality. A completed result can have `passed=false`.

## Cancellation and deadlines

`POST /runs/{id}/cancel` cancels all still-active jobs for a queued run, invalidating leases transactionally. Completed jobs/results remain intact; terminal runs are unchanged. Synchronous runs return 409 for this operation. Cancellation of provider work already in flight is best effort: a heartbeat detects the lost claim and requests task cancellation; any late completion is rejected regardless of heartbeat timing.

Per-provider-operation application timeout: 30 seconds. Whole evaluation attempt deadline: 45 seconds, distinct from its lease. The SDK receives a request timeout; explicit connection-versus-read timeout configuration remains future work. Database connection timeout is five seconds with ten-second command/statement bounds. There is no overall run deadline yet.

SIGINT/SIGTERM stops all lanes from starting subsequent work. Active attempts share one 50-second drain deadline, after which cancellation is requested and remaining leases are left for recovery. A claim already in flight may commit during shutdown; provider execution does not start after observing stop. This is cooperative shutdown, not a hard process-kill deadline. Database/heartbeat failure prevents unconditional result acceptance; the final database guard is always authoritative. Controlled shutdown while evaluations are blocked is tested, including successful drain and forced cancellation/recovery. Live database outages and production shutdown/network partitions remain additional reliability checks.

Application transition guards do not prevent privileged manual SQL from violating lifecycle rules. Use supported queue operations; PostgreSQL enforces structural status/lease/count/relationship constraints but no transition-history trigger.

## Concurrency semantics

One process owns a fixed number of lane tasks plus one recovery task. Each occupied lane owns evaluation, heartbeat and lease-watch tasks; no task is scheduled for every database job and no extra job is claimed ahead of lane capacity. Recovery polling is independent of lane execution. Polling defaults to one second. The API's execution slots, number of processes, database connections and provider requests are separate quantities. A worker's database engine retains its five-connection cap, while evaluation concurrency can be 16. Generation and judgment remain sequential within each evaluation. Multiple processes or synchronous API traffic multiply total concurrency; no global provider limiter exists.

WorkerMetrics records active/peak actual evaluations and started evaluations within one event loop; it excludes pending work and final persistence. A shutdown-abandoned claim consumes a persisted attempt but does not increment started-evaluation metrics. Metrics return to zero on success, failure, timeout or cancellation. Metrics are logged on worker shutdown and are not provider usage/cost totals.

## Milestone 5 — overall deadline and connection interruption

New queued runs have a persisted overall deadline, default 900 seconds. POST /queued-runs accepts run_timeout_seconds (integer 1–3600). This deadline is independent of provider, attempt and lease deadlines. After expiry, claims/renewals/completion are rejected even before the recovery loop marks the run CANCELED with error_category=run_timeout. Recovery retains successful earlier results and cancels active jobs. Older migrated runs with NULL deadlines are not retroactively expired.

Database pool health checks replace stale connections on checkout. Controlled tests make the dedicated test database refuse connections and terminate its backends; the worker cancels the affected provider task, reconnects after restoration and recovers its lease. This does not guarantee availability during an outage or protect against storage loss. Stop old API/worker processes before applying schema-changing releases, and restart them from the new code; mixed-version worker behavior is not supported.
