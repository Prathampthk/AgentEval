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

Retryable provider failures use full-jitter capped exponential backoff: delay uniformly between 0 and `min(60, 2 ** (attempt - 1))` seconds. Default maximum is three attempts. Attempts and next eligible time persist across restarts. Permanent errors fail immediately. Valid provider Retry-After guidance sets a lower bound on retry delay; guidance beyond the supported delay budget terminates rather than retrying early. A retry attempt repeats the whole generation/judgment evaluation; a successful generation followed by judge failure can incur repeated generation charges.

The worker scans up to 100 expired leases per iteration. Expired jobs return to PENDING when budget remains; otherwise they become FAILED with `lease_expired`. Old workers cannot renew or save over a later claim. A worker crash after receiving a response can repeat an external call: execution is at-least-once attempts, with fenced result persistence, **not exactly-once provider execution**. Finite attempt budgets can end in failure.

Successful case results remain visible when other cases fail or the run is canceled. Once every job is terminal, any failed job makes the run FAILED; otherwise canceled jobs make it CANCELED; otherwise it is COMPLETED. These are execution outcomes, not answer quality. A completed result can have `passed=false`.

## Cancellation and deadlines

`POST /runs/{id}/cancel` cancels all still-active jobs for a queued run, invalidating leases transactionally. Completed jobs/results remain intact; terminal runs are unchanged. Synchronous runs return 409 for this operation. Cancellation of provider work already in flight is best effort: a heartbeat detects the lost claim and requests task cancellation; any late completion is rejected regardless of heartbeat timing.

Per-provider-operation application timeout: 30 seconds. Whole evaluation attempt deadline: 45 seconds, distinct from its lease. The SDK receives a request timeout; HTTPX connection/pool acquisition is capped separately at five seconds. Database connection timeout is five seconds with ten-second command/statement bounds. New queued runs have an overall 900-second default deadline, configurable from 1–3600 seconds; see the milestone 5 section.

SIGINT/SIGTERM stops all lanes from starting subsequent work. Active attempts share one 50-second drain deadline, after which cancellation is requested and remaining leases are left for recovery. A claim already in flight may commit during shutdown; provider execution does not start after observing stop. This is cooperative shutdown, not a hard process-kill deadline. Database/heartbeat failure prevents unconditional result acceptance; the final database guard is always authoritative. Controlled shutdown while evaluations are blocked is tested, including successful drain and forced cancellation/recovery. Live database outages and production shutdown/network partitions remain additional reliability checks.

Application transition guards do not prevent privileged manual SQL from violating lifecycle rules. Use supported queue operations; PostgreSQL enforces structural status/lease/count/relationship constraints but no transition-history trigger.

## Concurrency semantics

One process owns a fixed number of lane tasks plus one recovery task. Each occupied lane owns evaluation, heartbeat and lease-watch tasks; no task is scheduled for every database job and no extra job is claimed ahead of lane capacity. Recovery polling is independent of lane execution. Polling defaults to one second. The API's execution slots, number of processes, database connections and provider requests are separate quantities. A worker's database engine retains its five-connection cap, while evaluation concurrency can be 16. Generation and judgment remain sequential within each evaluation. Multiple processes or synchronous API traffic multiply total concurrency; no global provider limiter exists.

WorkerMetrics records active/peak actual evaluations and started evaluations within one event loop; it excludes pending work and final persistence. A shutdown-abandoned claim consumes a persisted attempt but does not increment started-evaluation metrics. Metrics return to zero on success, failure, timeout or cancellation. Metrics are logged on worker shutdown and are not provider usage/cost totals.

## Milestone 5 — overall deadline and connection interruption

New queued runs have a persisted overall deadline, default 900 seconds. POST /queued-runs accepts run_timeout_seconds (integer 1–3600). This deadline is independent of provider, attempt and lease deadlines. After expiry, claims/renewals/completion are rejected even before the recovery loop marks the run CANCELED with error_category=run_timeout. Recovery retains successful earlier results and cancels active jobs. Older migrated runs with NULL deadlines are not retroactively expired.

Database pool health checks replace stale connections on checkout. Controlled tests make the dedicated test database refuse connections and terminate its backends; the worker cancels the affected provider task, reconnects after restoration and recovers its lease. This does not guarantee availability during an outage or protect against storage loss. Stop old API/worker processes before applying schema-changing releases, and restart them from the new code; mixed-version worker behavior is not supported.

## Final retry/timeout review

The Gemini adapter now preserves valid Retry-After seconds or HTTP-date guidance. Worker delay is at least that guidance and at least its jittered backoff; hints over the supported one-hour retry-delay budget terminate the attempt policy rather than retrying early. Invalid hints fall back to normal backoff. No provider content or raw error text is logged.

The pinned HTTPX-backed SDK configuration uses a public request hook to cap connection establishment and pool acquisition at five seconds while retaining the configured read/write request timeout (30 seconds by default). The outer application timeout still bounds the whole provider operation. Controlled HTTPX tests verify these separate phases; live behavior remains unverified until secure credential binding.

## Platform verification update

The queue capacity is configurable through `AGENTEVAL_QUEUE_CAPACITY` (default 1,000 active jobs, process startup validates 1–100,000). Capacity is installation-wide **provided every submitting API uses the same configured value and admission protocol**. Pending, running and delayed retries consume capacity. No in-memory prefetch queue exists: one free lane claims one job. Admission lock contention is bounded at one second and returns HTTP 503 with `Retry-After: 1`; capacity exhaustion returns 429 with `Retry-After: 5`. Clients retry ambiguous submissions with the same idempotency key. This bounds stored active work, not request bytes or historical storage; retention and ingress connection/rate limits remain deployment responsibilities.

Lease guards now acquire the job row lock **before** checking the database clock, token and owner. Otherwise a predicate evaluated before a lock wait could permit acknowledgment after expiry. Completion/failure retain run-before-job lock order; renewal takes only the job lock. Real PostgreSQL tests hold that lock past expiry and verify rejection for completion, failure and renewal.

Independent process tests use explicit filesystem barriers and database-observed lock waits rather than arbitrary sleeps. Crashes are abrupt process exits: before execution, after an fsynced simulated external effect but before result commit, and after commit but before returning acknowledgment. Replacement workers produce one accepted database result. The middle scenario produces **two external effects**. Fencing prevents a stale process from committing; it cannot undo an already sent external request. Cancellation is similarly best effort for external work and final for accepted database writes.

Delivery is a durable, bounded-retry attempt protocol under PostgreSQL availability/durability assumptions. It is not unconditional eventual delivery: permanent errors, exhausted attempts, cancellation and overall deadlines terminate work. PostgreSQL acknowledgment durability depends on its storage, WAL/fsync/synchronous-commit settings and backup/replication configuration. This repository does not prove host-loss recovery, HA or backup restoration. Lost HTTP acknowledgments are resolved by idempotent replay while the key/history remains stored. Retrying provider effects safely requires provider-supported idempotency or domain reconciliation; AgentEval cannot guarantee exactly-once external execution.
