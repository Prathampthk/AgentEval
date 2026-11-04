# Engineering decisions

## ADR 001 — Start with request-scoped evaluation

Status: accepted for milestone 1 following user approval, 2026-11-03.

Context: the repository was empty, and both evaluation semantics and durable execution needed implementation. Building both immediately would make failures harder to isolate.

Decision: implement a local FastAPI generation/judgment slice with independent service logic, strict schemas, an explicit fake provider and the official async GenAI adapter. Return results directly. Keep data contracts small and preserve answer-key isolation.

Alternatives: build a PostgreSQL queue first; create an entire dashboard; use an agent framework. These delay validation of the actual evaluation rules or introduce unnecessary dependencies.

Trade-offs: request-scoped work is lost on process exit; dataset version labels are not durable immutable datasets. A four-slot API admission limit protects this demonstration process, not a multi-process deployment.

Consequences: persistence is the next useful milestone. No durable-processing or performance claims can be made. Live-provider access is optional for this increment. Human labeling must be performed by actual people later.

Learning takeaway: separate the meaning of work from the machinery that schedules it.

## ADR 002 — PostgreSQL persistence before durable scheduling

Status: accepted for milestone 2 under the user's instruction to continue the project, 2026-11-03. This follows the previously proposed PostgreSQL/SQLAlchemy/Alembic architecture.

Problem: request-scoped results were lost after every response, preventing inspection across restarts or later comparison.

Decision: persist dataset versions, cases, runs and normalized results using async SQLAlchemy and explicit Alembic migrations. Keep existing evaluation semantics unchanged. Commit a run first, make provider calls without a database transaction, then atomically store all results and completion. Store FAILED with a sanitized category when a provider call fails. Dataset creation uses a unique name/version and content hash to deduplicate equivalent submissions.

Alternatives: keep everything in JSON files (simple, but weak concurrency and relational integrity); hold a transaction through provider work (simpler control flow, but ties up connections and locks); add workers now (larger increment mixing persistence with scheduling semantics).

Verification: real PostgreSQL tests cover competing dataset creates, integrity violations, rollback, provider failure and new-instance reads. A real HTTP process restart verifies stored data remains readable. Migration round-trips and model agreement are checked.

Trade-offs: all results from an incomplete run are discarded; individual progress is not exposed. A process crash or database outage can leave RUNNING records. Retrying POST /runs can create a new run and repeat provider charges. These are explicit limits until durable jobs and idempotency are implemented. Up to 20 cases run sequentially per request, sharing the existing four-request process-local capacity bound. Large results and long requests are reasons to move to workers, not reasons to claim durability now.

Learning takeaway: a saved outcome and a recoverable task are different capabilities. Database persistence is a prerequisite for durable scheduling, not proof of it.

## ADR 003 — Add a PostgreSQL queue with fenced sequential execution

Status: implemented under the approved roadmap continuation, 2026-11-03.

Problem: saving completed evaluations did not make unfinished work recoverable. A request or process could disappear after creating a run.

Decision: add /queued-runs separately from existing synchronous routes. Commit submission and jobs atomically; use a unique idempotency key, short SKIP LOCKED claims, database-clock leases, owner/token guards, and unique result constraints. Serialize admission with a transaction advisory lock and aggregate updates with per-run locks. A separate sequential worker executes evaluations, renews leases, persists retry schedules and recovers expired jobs.

Alternatives: replace all existing routes at once (breaking change); use an in-memory queue (not durable); add a separate broker (unnecessary infrastructure for the initial workload); implement the full concurrency pool now (larger correctness surface).

Verification: real PostgreSQL concurrency and failure tests, actual process exit, post-response crash-window simulation, and a separate API/worker HTTP smoke test. See MILESTONE_3_EVIDENCE.md.

Trade-offs: queue admission is serialized and may become a bottleneck; completion aggregates serialize within a run. Sequential execution intentionally delays throughput work. Provider calls can repeat after failures. Retries repeat generation and judgment together. There is no run-level deadline, Retry-After support, global provider cap or complete outage/shutdown evidence yet. These remain explicit follow-up work.

Learning takeaway: a lease is temporary permission, not permanent ownership. Every final write must prove that permission is still valid.

## ADR 004 — Fixed worker loops for bounded asynchronous execution

Status: implemented under roadmap continuation, 2026-11-03.

Problem: the sequential worker limited overlap, while creating a task for every queued job would make memory and scheduling grow with backlog size.

Decision: launch a fixed number of lane loops plus one recovery loop. Each lane claims one job, evaluates and persists it, then claims again. The existing lease/heartbeat/fenced-write path is reused. `AGENTEVAL_WORKER_CONCURRENCY` accepts 1–16 and defaults to 1. Metrics count current/peak evaluations and started evaluations within one process. No database migration or additional service is required.

Alternatives: create a task per job behind a semaphore (limits active calls but still permits growing task count); claim batches ahead of capacity (leases can expire while waiting locally); introduce a separate scheduler/broker (not needed for the current workload).

Verification: a real PostgreSQL queue holds 120 jobs; a controlled barrier proves 16 evaluations overlap while 104 jobs stay unclaimed. Tests also assert task bounds, successful draining, timeout cancellation/recovery, failure isolation and lane reuse after cancellation. Invalid configuration fails before tasks start.

Trade-offs: polling remains one second by default; it can add queue latency. The five-connection database pool is independent of evaluation concurrency and may become a bottleneck under load. Admission and per-run aggregation still serialize database operations. The cap is per worker process: multiple workers and the API's synchronous endpoints can exceed 16 combined provider calls. The benchmark must use one configured worker and avoid concurrent synchronous evaluations. Shutdown is cooperative, with one shared 50-second drain deadline rather than 50 seconds per lane. Claims already in flight at shutdown can commit; they are left leased without starting provider work.

Learning takeaway: limiting simultaneous work and limiting scheduled work are different requirements. A fixed set of consumers provides both.

## ADR — post-lock lease checks and bounded admission

**Context:** PostgreSQL may evaluate a volatile clock predicate before waiting for a row lock. A lease can expire while a result writer waits. Unbounded admission lock waits also hide overload.

**Decision:** Acquire the job row lock before evaluating owner/token/status/deadline/expiry guards. Keep run-before-job ordering for finalization. Bound admission lock waits to one second, expose retry hints, and configure the durable active-job capacity.

**Alternatives:** A more complex single-statement CTE or triggers could enforce guards; an external broker could handle admission. Neither is needed to fix this demonstrated race.

**Trade-offs:** One extra short SQL statement per guarded write; installation-wide admission serialization; run summaries remain serialized. Every submission path must follow the same protocol.

**Consequences:** Tests deliberately block each guarded write past expiry and prove rejection. Capacity rejection creates no partial run. HTTP clients retain their key across retries.

## ADR — independent-process benchmark and deployment isolation

**Context:** Async lane tests do not demonstrate process isolation or measure process-scaling costs. Runtime processes should not need DDL credentials.

**Decision:** Use real independent interpreters, one lane each, at 1/4/8/16, preserve raw reports and separate crash recovery probes. Deploy one-shot migrations separately from restricted runtime roles. Keep the local Compose API loopback-only and simulated by default.

**Alternatives:** Threads or many async lanes are useful but answer a different performance question; an orchestration framework adds unnecessary complexity.

**Trade-offs:** Process startup and memory costs increase (startup excluded from throughput window and stated explicitly); Docker resource samples are container-wide and coarse. No HA or public authentication is added.

**Consequences:** Report throughput and completion latency honestly, including scaling regressions. Production rollout still requires ingress security, backups and operational validation.
