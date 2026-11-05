# Résumé claims audit

**Latest platform review:** see [engineering review](PLATFORM_REVIEW.md), [delivery semantics](JOB_EXECUTION_SEMANTICS.md), and [evidence-backed achievements](../RESUME_EVIDENCE.md). Historical performance numbers below describe simulations, not live Gemini. The historical configured-16 run observed peak **5** active evaluations. No human labels or exactly-once external-execution claim is verified.

Initial audit date: 2026-11-03. This began as a new implementation: the checkout initially contained no source files, manifests, tests, migrations, or CI workflows. The earlier remote inspection returned no refs; fetching `main` failed because the ref did not exist. At that time there was no request lifecycle to trace or test suite to run. Current implementation status is below; milestone updates retain the history.

The original target statements below are not valid verbatim résumé claims. Current scoped evidence is in the latest platform update and root `RESUME_EVIDENCE.md`; earlier milestone entries are retained as history.

| Claim | Existing implementation | Missing functionality | Verification method | Evidence | Status |
|---|---|---|---|---|---|
| Engineered a PostgreSQL-backed asynchronous evaluation engine with persistent job queues, bounded concurrency, idempotent execution, and crash recovery to reliably process LLM regression workloads. | jobs.py: submit/claim/renew/complete/fail/recover/cancel; worker.py: run_once/serve; migrations 0001–0004 | Public operational validation, host/storage failure recovery and external-provider behavior | Independent-process PostgreSQL tests, post-lock expiry tests, outage tests and process benchmark | tests/integration/test_process_guarantees.py; RESUME_EVIDENCE.md; reports/platform-benchmark.json | PARTIAL (scoped queue guarantees verified locally) |
| Improved LLM evaluation throughput by 2.8× over sequential execution using 16 bounded asynchronous workers, exponential-backoff retries, and caching; benchmarked 1,000 evaluations while measuring P95 latency and token usage. | benchmark.py, worker.py, reports/benchmark.json | Literal target wording differs: historical 3.091× simulated ratio used configured 16 lanes but observed peak 5; caching disabled, billable tokens unavailable. New actual-process sweep is reported separately | Equivalent 1,000-job simulated workloads at concurrency 1 and 16, repeated runs, raw artifacts, latency and throughput reporting; separate live-provider results | BENCHMARK_REPORT.md: 3 repetitions, 1,000 jobs per configuration; live usage unavailable | PARTIAL |
| Built GitHub Actions regression gates and automated failure-recovery tests; validated Gemini-based LLM judges against 50 human-labeled responses, measuring agreement and false-positive rates. | Deterministic CI definition and selected failure-recovery tests | Actual human labels and representative live judge measurements | Deterministic gate fixtures including PASS/FAIL/INCONCLUSIVE; recovery tests; confusion matrix with declared positive class and actual labeled sample size | reports/hosted-ci-current.json; reports/live-gemini-smoke.json; no human accuracy report | PARTIAL |

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

## Evidence-supported wording after final review

- VERIFIED within controlled tests: “Implemented a PostgreSQL-backed durable evaluation queue with atomic claims, idempotent submission, lease fencing, cancellation and recovery; tested worker crashes and database connection interruptions.”
- VERIFIED for simulation only: “Measured 3.09× mean completion-time speedup at concurrency 16 over sequential execution on repeated 1,000-job simulated workloads, reporting latency distributions and retries.”
- PARTIAL: CI regression checks are implemented and tested locally, but hosted runs are unverified. Human judge agreement is BLOCKED with zero labels. No 50-human-label, live-Gemini-accuracy, caching-speedup or exactly-once external-call claim is verified.

Final local suite: 114 backend tests and one core Chromium workflow passed. See DELIVERABLES.md for the full status matrix.


## Latest platform verification — 2026-11-04 UTC

The final full suites passed **127 tests on the host and 127 inside the non-root container**, no failures/errors/skips and one dependency warning each. One Chromium workflow passed; formatting, lint, dependency consistency, deterministic regression gate, fresh-volume migration and HTTP smoke passed. Exact command/count/duration/test IDs and disclosed intermediate failures: `reports/platform-verification.json`.

| Target claim | Current evidence | Remaining gap | Status |
|---|---|---|---|
| Durable PostgreSQL engine, bounded execution, idempotency and crash recovery | `JobQueue.submit/claim/renew/complete/fail/recover/cancel`, `worker.run_once/serve`; independent-process tests, post-lock-expiry rejection, controlled connection interruptions and crash probes | External effects can repeat; host/storage/HA validation and public operational controls remain | VERIFIED for documented local queue guarantees; broader production reliability PARTIAL |
| 2.8× / 16 workers / caching / 1,000 evaluations / token usage | New sweep completed 12,000 jobs, 1,000 per variant, three reps at 1/4/8/16 OS processes; raw P50/P95 and PostgreSQL resources. Mean throughput 19.83 / 72.40 / 73.91 / 37.64 jobs/s respectively | No caching or live billable tokens; observed peak differs from configured capacity; 16-process outlier had extra retries and ten server-confirmed run-lock statement timeouts. Do not copy the original target | PARTIAL; use measured scoped wording in root RESUME_EVIDENCE.md |
| Hosted CI and 50-human-label judge validation | CI definitions and equivalent local checks, failure-injection tests and deterministic regression gate | Hosted execution NOT VERIFIED; zero actual human labels; no live judge accuracy | PARTIAL; human-validation claim BLOCKED |

The historical 3.091× ratio remains valid arithmetic for its single-process async-lane simulation, with configured-16 but observed peak five. The new process sweep is separate; retain all repetitions, including outliers. `RESUME_EVIDENCE.md`, `PLATFORM_REVIEW.md` and `PLATFORM_BENCHMARK_REPORT.md` supersede earlier milestone status summaries without erasing their historical evidence. No exactly-once external execution or production-ready claim is verified.


## Lock/CI follow-up

Both hosted workflows passed on `cb28a72` after correcting the public CA build-secret path for newer Bake filesystem policy. Every job step conclusion and artifact name/digest was observed via GitHub web pages; artifact contents were not downloaded. This closes the earlier hosted-execution gap for that source revision. Human labels/live judge quality remain blocked.

The full local suite now passes **130 tests**, including controlled PostgreSQL lock/timeout attribution and diagnostic redaction checks. Four instrumented 1,000-job variants at 4/16 independent processes completed with eleven planned retries each and no SQL errors. Increased run-lock waiting is verified; the original ten-second timeout cause remains unresolved because it did not recur. No execution-policy or exactly-once claim changed. Details and raw evidence: LOCK_CONTENTION_REVIEW.md and reports/lock-diagnostics-summary.json (paths relative to repository root for reports).


RAG follow-up: the full local suite now passes **134 tests**, zero failures/errors/skips, one dependency warning. Shared citation-preserving context bounds and provider HTTP 504 timeout handling correct the two known endpoint defects. Evidence: reports/rag-fixes-verification.json and RAG.md. No live-provider accuracy, token-cost or human-label claim follows.


Hosted follow-through: both workflows passed at application revision `0b84e4d` (runs 41768068596 and 41768068502); every step conclusion and artifact metadata was observed, artifact downloads were not. A controlled local dump/restore drill also passed for generated completed/pending jobs and idempotency state; it does not verify production disaster recovery or an RPO/RTO SLA. No human labels or live provider measurements were created.


## Current reconciliation — 2026-11-04

This update supersedes historical pending status above without changing historical measurements. Two offline wire-contract checks bring the prior local suite to 136 tests. Gemini judgment now uses `response_json_schema=Judgment.model_json_schema()`. `reports/live-gemini-smoke.json`, committed in `da60690`, records one completed sync and one completed queued `gemini-3.1-flash-lite` evaluation of the same case (queued attempt count one). This verifies a narrow connectivity/structured-output path, not judge accuracy or live throughput. Accepted-result metadata totals 418 input and 126 output tokens; failed/discarded requests are not included and no monetary cost or remaining budget is inferred. More paid calls require budget review.

Both hosted workflows passed at `da60690`; job/step conclusions and artifact metadata were inspected through the GitHub connector. Artifact contents were not downloaded. See `reports/hosted-ci-current.json`. The human study remains BLOCKED with zero supplied labels; live embeddings/RAG and public deployment safeguards remain separate unfinished work. The historical PostgreSQL timeout cause remains unresolved.

Portfolio increment: the final non-root container suite passed **140 tests**, zero failures/errors/skips, one dependency warning. Four new cases verify refusal of live/unready APIs before the demo mutates data. The actual fake-provider demonstration passed; human labels remain zero. Exact counts, source hashes and retained XML hash are in `reports/current-verification.json`. The separate local lock follow-up retained both 1,000-job variants without reproducing the timeout; the historical cause remains unresolved.

## Human labels completed; live collection remains pending — 2026-11-05

All fifty human decisions were supplied by the user, validated and frozen locally without edits: ten pass and forty fail. `reports/human-labels-completion.json` records provenance and the file hash; raw labels/reviewer identifiers remain ignored. `reports/judge_validation.json` now reflects 50 human labels and zero paired predictions, with null agreement/error rates. Earlier zero-label entries are historical. No human/AI accuracy claim is yet verified.

The user requested offline preparation while free-tier eligibility is uncertain. The collector now supports an offline shuffled sample plan, preserves successful responses/usage plus attempt metadata, refuses prior outputs and stops on the first failure with no retries. Live requests remain capped at ten per invocation; this is not a global quota or spending ledger. Existing environment-based API-key configuration supports a local user’s own key; no premium tier or public bring-your-own-key service is claimed.

Offline preparation verification: **148 full container tests passed**, zero failures/errors/skips, one existing warning; **91 host unit tests passed**, with 57 integration tests deselected and two dependency warnings. Ruff lint/format passed. Eight collector safeguards are included. The initial container packaging failure and correction are disclosed in `reports/judge-preparation-verification.json`. No new Gemini requests were made.
