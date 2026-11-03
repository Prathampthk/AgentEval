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
