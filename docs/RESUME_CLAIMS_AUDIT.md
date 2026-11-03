# Résumé claims audit

Initial audit date: 2026-11-03. This began as a new implementation: the checkout initially contained no source files, manifests, tests, migrations, or CI workflows. The earlier remote inspection returned no refs; fetching `main` failed because the ref did not exist. At that time there was no request lifecycle to trace or test suite to run. Current implementation status is below; milestone updates retain the history.

All statements below remain target-state claims, not verified résumé statements. Quantitative outcomes are NOT VERIFIED.

| Claim | Existing implementation | Missing functionality | Verification method | Evidence | Status |
|---|---|---|---|---|---|
| Engineered a PostgreSQL-backed asynchronous evaluation engine with persistent job queues, bounded concurrency, idempotent execution, and crash recovery to reliably process LLM regression workloads. | models.py, database.py, jobs.py, worker.py, migrations 0001–0002 | Broader database-outage/network-partition verification and workload-scale reliability | Real PostgreSQL concurrency/recovery tests; measured active-task bound | MILESTONE_4_EVIDENCE.md; current-run test XML | PARTIAL |
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

## Milestone 4 update — 2026-11-03

Claim 1 remains PARTIAL as a broad workload reliability claim: fixed-size asynchronous execution is now implemented, with an independently measured peak of 16 active evaluations and bounded task growth in a controlled 120-job PostgreSQL workload. Cancellation/failure frees capacity, and controlled shutdown preserves pending/leased work. Broader outage and workload-scale reliability remain for milestone 5.

Claim 2 remains MISSING as a quantitative performance claim: no 1,000-job benchmark, speedup, P95 latency or cache result has been measured. Concurrency correctness is not throughput evidence. Claim 3 remains PARTIAL; controlled failure tests exist, but no human labeling/judge report or quality regression gate is complete. Evidence: `docs/MILESTONE_4_EVIDENCE.md`, worker pool tests and current-run XML.

Milestone 5: controlled test-database connection refusal/termination and restoration now pass with automatic recovery. Overall deadlines fence late writes. See MILESTONE_5_EVIDENCE.md. Host/storage failures and arbitrary network partitions remain outside verified scope.

Milestone 6 tooling: four analysis tests pass with explicitly synthetic fixtures. There are 50 unlabeled examples and zero actual human labels. reports/judge_validation.json is BLOCKED with null agreement; no human-accuracy résumé claim is verified.

Milestone 7: real pgvector storage/retrieval and controlled simulated RAG evaluation are verified by 102 passing tests. Live Gemini embedding quality remains NOT VERIFIED. No new performance claim follows.

## Milestone 10 measured benchmark

The controlled PostgreSQL benchmark completed 1,000 jobs per configuration across three repetitions (6,000 accepted results). Mean completion: 40.401 s at concurrency 1 and 13.070 s at concurrency 16, ratio **3.091×**. Every variant recorded 11 injected retries and no exhausted jobs. Full distributions and raw records: reports/benchmark.json; method/report: BENCHMARK_METHODOLOGY.md and BENCHMARK_REPORT.md.

Do not copy the original 2.8×/caching target literally: caching was disabled, billable token usage was absent and no live Gemini throughput was measured. An evidence-supported alternative is: “Benchmarked a PostgreSQL-backed evaluation worker on repeated 1,000-job simulated workloads, measuring 3.09× mean completion-time speedup at concurrency 16 while recording latency distributions and retries.” Human-validation claims remain blocked on actual labels. Live Gemini behavior remains unverified.
