# Database schema — migrations 0001–0004

Implemented in `src/agenteval/models.py`, with explicit Alembic revisions `0001` and `0002` under `migrations/versions/`. No application `create_all` or automatic migration-on-start is used.

| Table | Keys, constraints, indexes | Relationships and lifecycle |
|---|---|---|
| datasets | UUID primary key; unique `(name, version)`; SHA-256 content hash | Owns an atomic dataset version and its test cases; no update/delete API |
| test_cases | UUID primary key; dataset foreign key; unique `(dataset_id, external_id)` and `(id, dataset_id)` | Holds question, expected answer, context and exact-match flag; reused by runs |
| evaluation_runs | UUID primary key; dataset foreign key; status/outcome checks; `(id, dataset_id)` uniqueness; dataset/creation index | Snapshots provider, model, rubric, simulation flag and settings; RUNNING becomes COMPLETED or FAILED |
| evaluation_results | UUID primary key; unique `(run_id, test_case_id)`; composite foreign keys to run and case with matching dataset | Stores validated answer, integer scores, explanation, pass/exact-match flags, latencies and nullable token counts |

Score constraints enforce 0–2; latency constraints require finite nonnegative values; token counts are nullable and otherwise nonnegative. Composite foreign keys prevent a result from connecting a run to a case in a different dataset. The case-uniqueness indexes support dataset queries; result uniqueness supports run-detail queries. Dataset foreign keys restrict deletion; deleting a run cascades to its owned results. No retention/deletion endpoint or scheduled retention process exists yet.

`POST /datasets` inserts the dataset and cases together. Content hashing uses sorted, normalized case inputs, independent of input order. Repeating the same name/version and content returns the existing dataset; conflicting content returns HTTP 409. PostgreSQL uniqueness and `ON CONFLICT` handle concurrent creates. This deduplication applies only to dataset creation, not run submission.

Dataset immutability is an API contract: there are no mutation routes. Privileged direct SQL can still change records; the database does not yet have immutability triggers. Do not manually change published dataset contents. Important data integrity rules above are database-enforced.

A run is committed before provider calls. No database transaction or connection remains open during those calls. Results and COMPLETED status are committed in one transaction; failure rolls back both. Retrieval uses a read-only repeatable-read transaction so status and results come from one snapshot. Provider failure records FAILED without partial results. Terminal-state checks prevent service methods from overwriting completed runs; these are application guards, not database transition triggers.

The local Docker helper generates protected, ignored configuration under `.local/`, a non-superuser DML application role, and separate development/test databases. Schema administration uses a separate administrative URL. The application role has no migration ownership or superuser permission; administrative credentials are not injected by the runtime `run` helper. This is local development infrastructure, not production credential management. For an external database, set URLs securely; runtime needs `AGENTEVAL_DATABASE_URL`, migrations may use `AGENTEVAL_MIGRATION_DATABASE_URL`.

Jobs, leases, idempotent queued submission and expired-lease recovery are implemented in milestone 3. Label/document/vector tables and baseline comparisons remain in the roadmap. Store no credentials in dataset/run configuration. Treat stored text as potentially sensitive: use controlled examples, and plan retention before accepting private datasets.

## Durable-job schema additions

`evaluation_jobs` adds UUID identity, run/case/dataset composite relationships, unique run/case identity, status/attempt/lease/completion checks, persisted eligibility, timestamps and error categories. Partial indexes support eligible PENDING jobs and expired RUNNING leases. Results optionally reference a job through a unique job ID and a composite foreign key matching its run/case/dataset. Existing synchronous results keep NULL job IDs.

Runs now include execution mode, globally unique nullable submission key and paired payload hash. CANCELED is a valid terminal run state. Migration `0002` preserves existing synchronous runs and results. Its downgrade refuses to discard queued execution history: archive or remove that history explicitly before downgrading. No automated destructive cleanup is performed.

Synchronous run/result transactions retain the milestone 2 behavior. Queued completion commits one guarded job and result plus run aggregate together; completed case results survive failure/cancellation of other cases. See JOB_EXECUTION_SEMANTICS.md for locking, admission and recovery semantics.

## Subsequent migrations

0003 adds nullable run deadline_at; new queued submissions populate it and older NULL-deadline runs retain previous semantics. 0004 installs pgvector and adds documents (UUID, title/content hash uniqueness) and chunks (document FK/index, position/provider/model uniqueness, 768-dimensional vectors). Exact cosine retrieval filters by embedding provider/model. Document deletion cascades to chunks; no retention/deletion endpoint is exposed. See RAG.md for boundaries.
