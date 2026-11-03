# Architecture — milestone 3

## Current state

The initial audit found an empty repository. Milestone 1 now implements request-scoped evaluation in api.py, service.py, domain.py, providers.py and gemini.py. The durable lifecycle below remains proposed. Milestone 2 adds database.py, models.py, persistent_runs.py, persistence_schemas.py and Alembic migrations. See the milestone evidence documents for verified scope.

## Problem and decision

AgentEval needs both trustworthy evaluation and reliable execution. Use a Python modular monolith, with FastAPI and a separate asyncio worker entry point sharing application code and PostgreSQL. This keeps transactions and debugging understandable without introducing a broker or distributed services.

Proposed layout:

```text
src/agenteval/
  api/             # routes, schemas, HTTP error mapping
  application/     # evaluation orchestration, submissions, comparisons
  domain/          # state transitions, rubric and regression rules
  infrastructure/  # SQLAlchemy repositories, Gemini adapter
  worker/          # claim loop, leases, bounded execution, shutdown
migrations/        # Alembic revisions
tests/             # unit, provider contract, PostgreSQL integration, reliability
frontend/          # React dashboard, later milestone
benchmarks/        # controlled simulation and raw reports, later milestone
```

Domain code depends on neither FastAPI nor provider SDKs. Application services depend on small provider/repository contracts. Infrastructure implements those contracts; entry points wire dependencies. Avoid a generic framework or repository abstraction for every table.

## Alternatives and trade-offs

- FastAPI background tasks are simpler but do not survive process termination; suitable only for disposable work.
- Celery plus Redis is mature but adds operational state and another failure boundary. PostgreSQL already provides the durable state this initial workload needs.
- A single API process can execute evaluations initially; durable work will move to a separate worker before reliability claims are made.
- PostgreSQL polling adds database load and scheduling latency. Start with indexed eligibility queries and bounded batches; measure before introducing a broker.

## Proposed request lifecycle

Validate request → transactionally persist immutable run configuration and jobs → return run ID → worker atomically claims eligible work → commit claim → call provider outside transaction → validate evaluation output → transactionally save result if lease token is current → expose results and comparison.

This is the target lifecycle, not existing behavior. The current implementation uses request/response execution (with asynchronous I/O). Persisted /runs records configuration before provider calls, then commits all results and completion together. The /evaluations endpoint remains stateless. Milestone 3 adds durable /queued-runs and a separate sequential worker in jobs.py and worker.py. Configurable parallel execution remains future work.

## Three largest risks

1. **Duplicate effects and stale writes.** A worker can receive a paid provider response and crash before committing. Recovery can repeat the external call. Use bounded attempts, persisted retry schedules, lease fencing, and unique result constraints. Verify crash windows with real PostgreSQL; promise at-least-once attempts with guarded result writes, not exactly-once provider execution.
2. **Misleading quality decisions.** A judge can be biased, unstable, or wrong. Version rubrics and datasets, keep answer keys out of generation, separate infrastructure errors from quality failures, require compatible comparisons, and use INCONCLUSIVE when coverage is inadequate. Actual human labels must come from people.
3. **Concurrency and cost amplification.** Multiple processes multiply local limits; retries amplify traffic. Start with one worker process and a bounded pool, explicit admission limits, request/job deadlines, and retry budgets. Instrument maximum active evaluations and in-flight requests. Live-provider benchmarks require explicit budget and usable credentials.

## Smallest useful implementation milestone

Build a local FastAPI evaluation slice with a validated versioned dataset input, one generation operation, structured judgment, deterministic checks, a fake provider, and the official Google GenAI adapter. Return results directly; no persistence or durability claims yet. Do not pass expected answers to generation. Expose liveness separately from provider readiness.

Verification: deterministic tests cover valid evaluation, invalid judge output, provider timeout/failure, absent usage data, and answer-key isolation; a local HTTP smoke test exercises evaluation with the fake provider. SDK contract tests use controlled responses. A real Gemini call is optional and remains NOT VERIFIED until credentials and a chosen model are available.

Learning takeaway: validate what an evaluation means before making its execution durable. A queue can reliably execute a flawed evaluation.

The user approved milestone 1 on 2026-11-03. Durable execution remains a later milestone; seek approval before major architectural changes.

Provider construction now lives in runtime.py so API and worker share configuration without importing HTTP routes into worker logic. Durable queued requests return before provider execution. See ADR 003 for the implemented locking and failure model.
