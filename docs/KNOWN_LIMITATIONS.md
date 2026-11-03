# Known limitations and evidence boundaries

- Local/controlled demonstration only: no authentication or multi-tenancy. Do not expose submission endpoints publicly. Process-local limits and queue admission are not public abuse prevention.
- Live Gemini generation/judgment and embeddings remain unverified until credentials/model are securely configured and budgeted calls succeed. SDK contract tests and fake-provider results do not establish live quality.
- The human study has prepared examples and analysis tooling, but zero actual human labels. Agreement, false-positive and false-negative rates are unmeasured; reports explicitly say BLOCKED.
- Only /queued-runs is durable; synchronous /runs, /evaluations and RAG requests can be interrupted without automatic resumption. Old migrated runs with NULL deadlines retain earlier timeout semantics.
- Fenced persistence does not prevent duplicate external calls after crashes or uncertainty. Stored token usage covers accepted results, not discarded attempts or a complete cost ledger.
- Concurrency is limited per worker process (1–16), not globally. Multiple workers and synchronous API requests multiply traffic. Valid Retry-After guidance is respected within the supported retry budget; full-jitter backoff and finite budgets are implemented.
- Controlled database connection refusal, backend termination, crashes, leases and shutdown are tested. Arbitrary network partitions, host/storage loss and production deployment reliability are not guaranteed.
- Dataset immutability and terminal transitions are enforced through supported application operations; privileged direct SQL can bypass transition history. Structural constraints remain database-enforced.
- The RAG corpus is deliberately small; exact cosine search has no scale claim. Fake embeddings are word hashes, not semantic model evidence. RAG routes are not background jobs. Citation faithfulness is not independently calibrated.
- Regression thresholds are configurable demonstration policies, not statistical significance tests. Different judge models/datasets are incompatible. Shared generation/judge models may correlate errors.
- Simulated benchmark results are not live Gemini throughput. Caching is disabled in the benchmark. No live monetary-cost estimate is fabricated. Peak RSS is process-wide/cumulative, not isolated per variant.
- Frontend end-to-end testing covers a core Chromium workflow; it is not exhaustive cross-browser accessibility testing. A pre-existing Starlette test-client deprecation warning remains.
- Dependency versions are pinned for tested Linux/Python 3.12 and Node 24. There is no cross-platform hashed Python lock or claim of a comprehensive third-party security audit.
- Hosted GitHub Actions execution has not been inspected here; local equivalent checks are verified. Optional live workflows need separate GitHub repository secret/variable configuration.
