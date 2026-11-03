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
