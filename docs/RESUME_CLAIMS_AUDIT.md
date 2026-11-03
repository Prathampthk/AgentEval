# Résumé claims audit

Initial audit date: 2026-11-03. This began as a new implementation: the checkout initially contained no source files, manifests, tests, migrations, or CI workflows. The earlier remote inspection returned no refs; fetching `main` failed because the ref did not exist. At that time there was no request lifecycle to trace or test suite to run. Current implementation status is below; milestone updates retain the history.

All statements below remain target-state claims, not verified résumé statements. Quantitative outcomes are NOT VERIFIED.

| Claim | Existing implementation | Missing functionality | Verification method | Evidence | Status |
|---|---|---|---|---|---|
| Engineered a PostgreSQL-backed asynchronous evaluation engine with persistent job queues, bounded concurrency, idempotent execution, and crash recovery to reliably process LLM regression workloads. | models.py, database.py, jobs.py, worker.py, migrations 0001–0002 | Configurable bounded parallel pool and broader outage/shutdown verification | Real PostgreSQL concurrency/recovery tests; measured active-task bound | MILESTONE_3_EVIDENCE.md; current-run test XML | PARTIAL |
| Improved LLM evaluation throughput by 2.8× over sequential execution using 16 bounded asynchronous workers, exponential-backoff retries, and caching; benchmarked 1,000 evaluations while measuring P95 latency and token usage. | None | Runner, baseline, retries, instrumentation, benchmark; caching only if justified | Equivalent 1,000-job simulated workloads at concurrency 1 and 16, repeated runs, raw artifacts, latency and throughput reporting; separate live-provider results | No benchmarks run; speedup and usage NOT VERIFIED | MISSING |
| Built GitHub Actions regression gates and automated failure-recovery tests; validated Gemini-based LLM judges against 50 human-labeled responses, measuring agreement and false-positive rates. | Deterministic CI definition and selected failure-recovery tests | Regression gate, GitHub-hosted run verification, actual human labels and judge analysis | Deterministic gate fixtures including PASS/FAIL/INCONCLUSIVE; recovery tests; confusion matrix with declared positive class and actual labeled sample size | MILESTONE_3_EVIDENCE.md; no human labels or judge report | PARTIAL |

Update this audit at each milestone with exact commands, artifact locations, limitations, and observed outcomes. Duplicate external API calls remain possible; never substitute an exactly-once claim for idempotent result persistence.

## Milestone 1 update — 2026-11-03

Implemented `src/agenteval/domain.py`, `service.py`, `providers.py`, `gemini.py` and `api.py`: request-scoped evaluation, simulated provider, Gemini adapter and validated structured judgment. This does not fulfill the durable engine, benchmark or human-validation claims above, which remain MISSING as complete claims. Basic deterministic CI configuration exists but has not run on GitHub and is not a regression gate.

Evidence: `docs/MILESTONE_1_EVIDENCE.md`; current-instance pytest XML at `artifacts/tests.xml` (ignored generated output). No live Gemini results, benchmarks or human labels exist.

## Milestone 2 update — 2026-11-03

Claim 1 is now PARTIAL: PostgreSQL dataset/run/result persistence and migration verification exist (`models.py`, `database.py`, `persistent_runs.py`, migration `0001`). Durable jobs, bounded worker execution, idempotent run submission and crash recovery remain missing. Dataset-create deduplication must not be described as idempotent job execution. Evidence: `docs/MILESTONE_2_EVIDENCE.md` and current-run XML. Claims 2 and 3 remain MISSING as complete claims; no benchmark, human-label report or quality regression gate exists.

## Milestone 3 update — 2026-11-03

Claim 1 remains PARTIAL overall: persistent queue, transactional claiming, idempotent queued submission, leases, fenced result writes, recovery of expired work and a sequential worker are now implemented and tested (`jobs.py`, `worker.py`, migration `0002`, `tests/integration/test_jobs.py`). Crash-before-execution uses an actual abruptly exiting subprocess; post-response interruption is simulated. Configurable bounded parallel execution and broader reliability scenarios remain outstanding. No exactly-once external-execution claim is valid.

Claim 2 remains MISSING: no 16-active benchmark, 1,000-job report or cache evidence. Claim 3 remains PARTIAL: deterministic CI configuration and selected automated failure-recovery tests exist, but GitHub-hosted execution, quality regression gates, human labels and agreement measurements are unverified/missing. Evidence: `docs/MILESTONE_3_EVIDENCE.md` and current-run XML.
