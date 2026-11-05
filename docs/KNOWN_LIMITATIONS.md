# Known limitations and evidence boundaries

- Local/controlled demonstration only: no authentication or multi-tenancy. Do not expose submission endpoints publicly. Process-local limits and queue admission are not public abuse prevention.
- Live Gemini generation/judgment has only two successful smoke evaluations of one simple case (`reports/live-gemini-smoke.json`). Live embeddings and RAG remain unverified. Neither this sample nor SDK contracts establish accuracy or throughput. Accepted-result usage is not a complete cost ledger; budget review is required before more paid calls.
- The human study has fifty validated user-supplied labels, but no paired judge predictions yet. Agreement, false-positive and false-negative rates are unmeasured; reports explicitly say BLOCKED.
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
- Both hosted workflows passed at `da60690`; step conclusions and artifact metadata were inspected through the GitHub connector, but artifact contents were not downloaded (`reports/hosted-ci-current.json`). Optional live workflows need separate GitHub repository secret/variable configuration.

## Platform review limits

- Process-local concurrency is not a distributed provider quota. Queue capacity requires consistent configuration across submitting APIs. History storage remains unbounded without retention operations.
- No authentication/TLS/public ingress abuse protection, HA or host/storage-loss recovery proof. A generated-data local dump/restore drill passed; production backup scheduling, offsite storage and RPO/RTO remain unverified. Compose is a loopback-only controlled deployment.
- Fencing controls database acceptance, never already emitted external effects; duplicate provider charges remain possible after crashes or judge-stage retries.
- Hosted CI success and two local live Gemini smoke evaluations are recorded; human judge accuracy remains unverified. Human labels are complete (50), but judge agreement remains unmeasured; the prepared set has only ten distinct questions with five variants each and is not representative of all applications.
- The historical RAG context overflow and generation-timeout misclassification are now corrected by a shared evidence budget and provider timeout handling; see RAG.md. Context truncation can still omit facts and is disclosed in the response. This does not establish general public-endpoint robustness.
- Runtime dependency vulnerability checks are point-in-time evidence, not security certification. Base images require ongoing updates and scanning.

The process sweep's first 16-worker repetition recovered extra attempts beyond the eleven injected provider failures. Server logs confirm ten run-row SELECT FOR UPDATE statement timeouts. All results were accepted eventually, but the prolonged lock-holder cause is unresolved and the benchmark actor did not capture INFO-level worker events. Investigate transaction/lock timing before increasing process counts in production. Higher process counts increased connection/lock pressure; the shared-host timings are variable.

The judge collector caps live requests per invocation, not across users, processes or repeated invocations. Pacing is not quota enforcement; free-tier eligibility is not inferable from the key. API-key switching is local environment configuration only, with no shared-server key ownership or browser secret storage.
