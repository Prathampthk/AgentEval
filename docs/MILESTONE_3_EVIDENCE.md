# Milestone 3 evidence

Validated 2026-11-03 in the current cloud instance using Python 3.12.14 and real PostgreSQL 17. Detailed semantics and limitations are in JOB_EXECUTION_SEMANTICS.md and RELIABILITY_TESTING.md.

- Full pytest suite: **68 passed**, zero failures/errors/skips. This includes 40 unit/provider tests and 28 real-PostgreSQL integration tests. Current-run machine-readable report: ignored `artifacts/tests.xml`.
- New PostgreSQL tests cover concurrent submission/claiming/admission, lease renewal and fencing, retry eligibility and exhaustion, permanent failures, cancellation, transaction rollback, terminal guards, worker model selection and simultaneous completion aggregation.
- A real worker subprocess exits abruptly after a committed claim; expired-lease recovery lets a replacement worker finish. A separate post-response/pre-persistence simulation records two provider generations but only one accepted result.
- Migration `0002` applied on top of the existing development schema; full migration round-trip and model agreement checks passed in the test suite. `alembic check` reported no new upgrade operations. Check-constraint edits were added explicitly because autogeneration does not detect those changes.
- Real HTTP smoke: submit with worker stopped; duplicate submission returns the original run; separately started worker claims and completes the job; HTTP result lookup reports one accepted passing simulated result.
- Original stateless HTTP smoke and previously stored dataset/result lookup still pass after the migration.
- Lint, formatting and dependency consistency checks passed.

This verifies selected durable-job behaviors, not the complete final platform. A single worker currently processes one evaluation at a time. No 16-worker performance claim, throughput benchmark, live Gemini result, RAG pipeline, human validation or deployed GitHub CI result is verified by these checks.

Completed source will be committed and pushed as a milestone; the environment configuration is saved separately and is not published by the agent.
