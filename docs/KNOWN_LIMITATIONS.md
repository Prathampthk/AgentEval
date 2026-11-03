# Known limitations

- PostgreSQL, migrations and dataset/run/result persistence are implemented. No durable jobs, idempotent run submission, leases, retries or recovery yet. Crashes can leave RUNNING records; no automatic resumption exists.
- No RAG, embeddings, React dashboard, run comparison, regression gate or benchmark yet.
- No human labels or judge agreement results. No performance or cost claims verified.
- Gemini adapter is tested against controlled SDK-shaped responses, not a live service. Key, selected model and destination access are still prerequisites for live use.
- No authentication; local/controlled demonstration only. Application limits are process-local and do not protect a public deployment from abuse or slow clients.
- Request-scoped execution can be lost when the process exits. Client disconnect is not a durable cancellation mechanism.
- The persisted dataset API enforces version immutability; privileged direct SQL is not protected by immutability triggers. Stateless /evaluations still accepts caller-provided version labels. Rubric pass thresholds are provisional.
- Current Starlette emits a deprecation warning for its httpx-based test client. Tests pass; dependency modernization can be handled in a separate reviewed change.
- Requirements are exact version pins for the tested Python 3.12 Linux environment, without a cross-platform hashed lock. Package TLS verification remains enabled.

- Persisted runs execute up to 20 cases sequentially within one HTTP request; 20 cases can require 40 provider calls. No run-level deadline or retained partial progress yet. Repeating a run submission creates new work.
