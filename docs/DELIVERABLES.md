# Deliverable status

The local portfolio demo is ready. This index supersedes earlier blocked-label/live-evidence status; original experiment reports remain historical evidence. See [completion and remaining work](PROJECT_COMPLETION.md).

| Deliverable | Current scope | Evidence |
|---|---|---|
| Backend, PostgreSQL and migrations | Implemented and integration-tested | [Database schema](DATABASE_SCHEMA.md), [latest implementation verification](../reports/private-refusal-verification.json) |
| Durable queue and bounded workers | Controlled idempotency, leases, fencing, recovery and shutdown | [Execution semantics](JOB_EXECUTION_SEMANTICS.md), [reliability](RELIABILITY_TESTING.md) |
| Gemini adapter | Offline contracts plus narrow live evidence | [Smoke record](../reports/live-gemini-smoke.json), [provider configuration](PROVIDER_CONFIGURATION.md) |
| Human judge study | 50 genuine labels paired; 10 development + 40 response-level validation matches | [Methodology and limitations](HUMAN_LABELING.md) |
| RAG and human review | Six synthetic documents, eight questions; user-reviewed support/abstention | [RAG](RAG.md), [review completion](../reports/rag-human-review-completion.json) |
| Regression checker | Deterministic PASS/FAIL/INCONCLUSIVE cases | [Regression policy](REGRESSION_POLICY.md) |
| Dashboard and demo | Core Chromium flow; repeated launcher and retained history | [Demo](DEMO.md), [rehearsal evidence](../reports/demo-readiness-verification.json) |
| Automated verification | Latest full local container suite: 232 passed; hosted checks passed at 3d20f0a | [Implementation checks](../reports/private-refusal-verification.json), [GitHub checks](https://github.com/Prathampthk/AgentEval/actions) |
| Simulated performance | Measured controlled async/process workloads; no live throughput claim | [Process report](PLATFORM_BENCHMARK_REPORT.md), [historical async report](BENCHMARK_REPORT.md) |
| Timeout investigation | Instrumentation/positive control verified; historical cause unresolved | [Lock review](LOCK_CONTENTION_REVIEW.md) |
| Private hosting preparation | Docker/TLS/auth/budget/local encrypted restore prepared; remote unprovisioned | [Private runbook](PRIVATE_SERVER.md), [request controls](SERVER_REQUEST_CONTROLS.md) |
| Claims and evidence | Scope and limitations disclosed | [Claims audit](RESUME_CLAIMS_AUDIT.md), [limitations](KNOWN_LIMITATIONS.md) |

New questions and repeated live trials need a fresh request allowance and genuine human ground truth. A server, offsite destination and provisioning approval are still required for remote operational acceptance. Neither is required to present the local fake-provider demo.
