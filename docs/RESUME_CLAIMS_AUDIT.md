# Résumé claims audit

Audit date: 2026-11-03. This is a new implementation. The checkout contains no source files, manifests, tests, migrations, or CI workflows. The earlier remote inspection returned no refs; fetching `main` failed because the ref did not exist. There is no evaluation request lifecycle to trace. No existing test suite could be run.

All statements below are targets, not accomplishments. Status is MISSING; quantitative outcomes are NOT VERIFIED.

| Claim | Existing implementation | Missing functionality | Verification method | Evidence | Status |
|---|---|---|---|---|---|
| Engineered a PostgreSQL-backed asynchronous evaluation engine with persistent job queues, bounded concurrency, idempotent execution, and crash recovery to reliably process LLM regression workloads. | None | Persistence, queue, workers, submission deduplication, fencing, recovery | Real PostgreSQL concurrency and restart tests; controlled provider failures; measured active-task bound | Repository inspection only; no execution evidence | MISSING |
| Improved LLM evaluation throughput by 2.8× over sequential execution using 16 bounded asynchronous workers, exponential-backoff retries, and caching; benchmarked 1,000 evaluations while measuring P95 latency and token usage. | None | Runner, baseline, retries, instrumentation, benchmark; caching only if justified | Equivalent 1,000-job simulated workloads at concurrency 1 and 16, repeated runs, raw artifacts, latency and throughput reporting; separate live-provider results | No benchmarks run; speedup and usage NOT VERIFIED | MISSING |
| Built GitHub Actions regression gates and automated failure-recovery tests; validated Gemini-based LLM judges against 50 human-labeled responses, measuring agreement and false-positive rates. | None | Regression policy, CI, failure injection, labeling rubric, actual human labels, judge analysis | Deterministic gate fixtures including PASS/FAIL/INCONCLUSIVE; recovery tests; confusion matrix with declared positive class and actual labeled sample size | No tests, labels, or reports exist | MISSING |

Update this audit at each milestone with exact commands, artifact locations, limitations, and observed outcomes. Duplicate external API calls remain possible; never substitute an exactly-once claim for idempotent result persistence.

## Milestone 1 update — 2026-11-03

Implemented `src/agenteval/domain.py`, `service.py`, `providers.py`, `gemini.py` and `api.py`: request-scoped evaluation, simulated provider, Gemini adapter and validated structured judgment. This does not fulfill the durable engine, benchmark or human-validation claims above, which remain MISSING as complete claims. Basic deterministic CI configuration exists but has not run on GitHub and is not a regression gate.

Evidence: `docs/MILESTONE_1_EVIDENCE.md`; current-instance pytest XML at `artifacts/tests.xml` (ignored generated output). No live Gemini results, benchmarks or human labels exist.

## Milestone 2 update — 2026-11-03

Claim 1 is now PARTIAL: PostgreSQL dataset/run/result persistence and migration verification exist (`models.py`, `database.py`, `persistent_runs.py`, migration `0001`). Durable jobs, bounded worker execution, idempotent run submission and crash recovery remain missing. Dataset-create deduplication must not be described as idempotent job execution. Evidence: `docs/MILESTONE_2_EVIDENCE.md` and current-run XML. Claims 2 and 3 remain MISSING as complete claims; no benchmark, human-label report or quality regression gate exists.
