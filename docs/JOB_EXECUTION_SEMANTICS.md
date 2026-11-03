# Proposed job semantics — awaiting approval

No worker exists. These are design decisions to validate during durable-job implementation.

- Legal transitions: PENDING → RUNNING or CANCELED; RUNNING → COMPLETED, FAILED, PENDING, or CANCELED. Terminal states do not reactivate. Retry exhaustion ends in FAILED.
- Claim eligible jobs using a short PostgreSQL transaction and `FOR UPDATE SKIP LOCKED`, updating status, attempt count, owner, expiration and a new fencing token before commit. Other claimers skip locked rows. Never hold the claim transaction during a provider call.
- Proposed defaults: 60-second lease, heartbeat every 15 seconds, 30-second provider request timeout and 45-second per-attempt job deadline. Configure connection timeout separately. Validate these values under load; database time determines lease eligibility.
- Renew and finalize only with matching job, RUNNING status, owner, token and unexpired lease. Cancellation invalidates the claim. Store result and completion together. A zero-row guarded update means the worker lost ownership and must discard its result.
- Recover expired RUNNING jobs to PENDING when budget remains, otherwise FAILED. Heartbeat database failure prevents accepting work after lease loss. A recovered attempt may repeat an already completed external call.
- Persist next execution time and attempts. Retry only classified transient failures, using capped exponential backoff with jitter and provider retry guidance. Permanent failures and malformed judge output fail explicitly by default. Proposed maximum: three attempts.
- Pending/retry-wait jobs cancel immediately. Running cancellation is best effort for external work, immediate for accepting future result writes. Completed jobs remain completed.
- Use a fixed number of worker coroutines, claiming only available capacity. Initial process-local concurrency is configurable, up to a benchmark target of 16. One worker process is required for the initial 16-active benchmark; there is no claimed global concurrency limit.
- Admission must be bounded transactionally. Choose limits and locking strategy when implementing submission, and test concurrent submissions against the bound. Do not rely on an unlocked COUNT query.
- Graceful shutdown stops claiming, drains within a deadline, then cancels tasks; remaining leases expire and recover. Persisted jobs survive process exit.
- Overall run deadline is distinct from job/provider/lease deadlines. Deadline expiration cancels remaining work and makes comparisons with insufficient results INCONCLUSIVE.

Required verification uses real PostgreSQL for competing claims, concurrent idempotency, transaction rollback, expired leases, fencing, cancellation and restart. Failure injection must cover response-before-persistence crashes. None of these guarantees is currently VERIFIED.
