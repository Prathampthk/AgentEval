# Known limitations

- PostgreSQL persistence and durable queued jobs are implemented. The original synchronous /runs path can still leave RUNNING records after a crash; only /queued-runs creates recoverable jobs. The worker supports a fixed pool of 1–16 active evaluations per process; the default remains one.
- No RAG, embeddings, React dashboard, run comparison, regression gate or benchmark yet.
- No human labels or judge agreement results. No performance or cost claims verified.
- Gemini adapter is tested against controlled SDK-shaped responses, not a live service. Key, selected model and destination access are still prerequisites for live use.
- No authentication; local/controlled demonstration only. Execution limits are process-local; the persistent queue cap is database-wide. These do not protect a public deployment from abuse or slow clients.
- Synchronous request-scoped execution can be lost when the process exits. Client disconnect is not a durable cancellation mechanism.
- The persisted dataset API enforces version immutability; privileged direct SQL is not protected by immutability triggers. Stateless /evaluations still accepts caller-provided version labels. Rubric pass thresholds are provisional.
- Current Starlette emits a deprecation warning for its httpx-based test client. Tests pass; dependency modernization can be handled in a separate reviewed change.
- Requirements are exact version pins for the tested Python 3.12 Linux environment, without a cross-platform hashed lock. Package TLS verification remains enabled.

- Synchronous /runs executes up to 20 cases sequentially within one HTTP request; 20 cases can require 40 provider calls. No run-level deadline or retained partial progress yet. Repeating a run submission creates new work.

- Expired queued jobs recover within a finite attempt budget; external calls can repeat. Queued idempotency is installation-wide and has no TTL; changing policy/model under a reused key produces conflict.
- Global provider concurrency limits, Retry-After guidance, run-wide deadlines and live database-outage recovery remain future work. Controlled shutdown/drain tests pass; production shutdown/network-partition behavior is not fully validated.
- Admission uses a serialized PostgreSQL advisory lock; scalability is not benchmarked. Provider/model changes require a matching worker to finish older queued work.

- Stored token usage describes accepted results only; discarded attempts and duplicated external requests are not a complete provider cost ledger.
