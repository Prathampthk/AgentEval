# Milestone 2 evidence

Validated 2026-11-03 in the current Linux cloud instance, Python 3.12.14, PostgreSQL 17 official image pinned by digest in `scripts/local_db.py`.

Implemented: immutable dataset-version API, case persistence, request-scoped evaluation runs, configuration snapshots, normalized results, lookup/list routes and explicit Alembic migration `0001`. The original stateless endpoint remains available.

| Check | Observed outcome |
|---|---|
| Full suite against a dedicated real PostgreSQL database | 50 passed, zero failures/errors/skips; 40 unit/provider tests and 10 integration tests |
| Migration downgrade to base, upgrade to head, repeated upgrade and `alembic check` | Passed in the test database |
| Five concurrent identical dataset creates | One dataset, one creator, two total cases; all callers receive the same dataset ID |
| Conflicting dataset version | Rejected, existing contents retained |
| Result insert failure after an earlier result insert | Entire transaction rolled back; no partial results or completed state |
| Foreign key mismatch across datasets | Rejected by `fk_result_case` |
| Provider failure on second case | FAILED run persisted, sanitized category retained, no partial result set |
| Provider-time database activity | No retained transaction or checked-out connection |
| Fresh API instance reading earlier data | Dataset and completed run round-trip unchanged |
| Real Uvicorn process restart | `smoke_persistence.py create` passed before shutdown; `check` passed after restart |
| Original stateless HTTP smoke | Passed with persistence configured |
| Database helper invoked again | Existing local configuration/container reused successfully |

Reproduce with the README commands. Current-run XML is in ignored `artifacts/tests.xml`; the smoke script retains only dataset/run identifiers in `artifacts/persistence-smoke.json`. CI is configured with a PostgreSQL service but has not run on GitHub. A Starlette test-client deprecation warning remains.

Limits: this demonstrates persisted data across API restarts, not unfinished-job recovery. Live Gemini, worker reliability, retries, RAG, benchmarks and human agreement remain NOT VERIFIED. Snapshot restoration into a later cloud task has not been tested as part of this milestone.
