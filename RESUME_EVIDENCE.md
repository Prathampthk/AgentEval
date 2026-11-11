# AgentEval — evidence-backed engineering achievements

**Latest follow-up:** the current non-root container suite passed 148 tests; 91 host unit tests also passed ([latest verification](reports/judge-preparation-verification.json)). Two offline Gemini wire-contract checks are included. The judge now supplies `Judgment.model_json_schema()` through `response_json_schema`. One synchronous and one queued live `gemini-3.1-flash-lite` evaluation succeeded on the same simple case ([committed evidence](reports/live-gemini-smoke.json)); this is connectivity/structured-output evidence only. Both hosted workflows passed at `da60690` ([current record](reports/hosted-ci-current.json)). The earlier 134-test RAG verification remains [recorded](reports/rag-fixes-verification.json). The preceding diagnostic milestone had 130 passing tests; 4,000 instrumented jobs completed with no SQL errors or unexpected retries. Both hosted workflows passed on `cb28a72` and application revision `0b84e4d`; artifact metadata was observed, contents not downloaded. Historical lock timeouts did not recur and their full cause remains unresolved. See [lock/CI review](docs/LOCK_CONTENTION_REVIEW.md), [hosted evidence](reports/hosted-ci-verification.json) and [diagnostic test record](reports/diagnostic-verification.json). Earlier measurements below retain their original scope.

Scope: controlled local PostgreSQL tests, independent worker processes, simulated providers and reproducible reports. This is not a production-readiness certification. No exactly-once external execution, live Gemini throughput, fabricated human labels or caching achievement is claimed.

## Verified implementation

- Implemented a PostgreSQL-backed durable queue with transactional `SKIP LOCKED` claims, persisted attempt budgets, installation-scoped idempotent submission, leased ownership, fenced acknowledgments, cancellation and recovery. Fixed a demonstrated expiry-during-lock-wait race; guards now check authority after acquiring the row lock.
- Added independent-process contention and abrupt-crash tests covering duplicate submission, exclusive claiming, stale ownership, cancellation, pre-execution failure, post-effect/pre-ack failure and post-commit acknowledgment loss. The post-effect crash produces two simulated external effects and one accepted database result, documenting the delivery boundary honestly.
- Added configurable active-job capacity, bounded admission lock waits, HTTP 429/503 retry guidance and fixed worker lanes with no per-pending-job task fan-out. The worker concurrency limit is process-local; a deployment-wide provider cap is not implemented.
- Added pinned container builds, PostgreSQL Compose deployment, separate migration administration, restricted runtime DML credentials, non-root/read-only application containers, loopback binding and connection/backlog limits. Deployment smoke checks cover readiness, dashboard, idempotent submission and accepted worker results.

Source: [`jobs.py`](src/agenteval/jobs.py), [`worker.py`](src/agenteval/worker.py), [process tests](tests/integration/test_process_guarantees.py), [delivery semantics](docs/JOB_EXECUTION_SEMANTICS.md), [deployment](docs/DEPLOYMENT.md). Implementation milestone: `6c0a44e`.

## Verification record

- Host full suite: **127 passed, zero failures/errors/skips**, one dependency deprecation warning; 44.01 seconds.
- Non-root container full suite: **127 passed, zero failures/errors/skips**, one dependency deprecation warning; 49.90 seconds.
- One Chromium workflow passed (43.1 seconds); frontend format/build, Python lint/format, dependency consistency and the deterministic regression gate passed.
- The equivalent CI container process-smoke configuration passed locally at 1/4/8/16 processes (64 throughput jobs plus four recovery probes); [raw smoke evidence](reports/platform-container-smoke.json).
- Fresh-volume Compose initialization, migrations, HTTP smoke and restricted runtime privileges passed. No superuser/create-role/create-database/schema-create privilege; job updates allowed and result deletion denied.
- Failed preliminary checks are disclosed in the [machine-readable verification record](reports/platform-verification.json), including the cold connection timeout and the corrected test-harness connection-lifecycle error. Final suites passed after correction.

Raw logs/XML remain under ignored `artifacts/`; the committed record includes exact counts, test IDs and XML hashes. Equivalent hosted CI execution was subsequently verified on `cb28a72`; see the latest follow-up above.

## Measured process benchmark

Completed **12,000 throughput jobs**: 1,000 identical logical jobs × four process counts × three repetitions. Every variant accepted all its results; no terminal job failures. One lane per independent process; caching disabled and no billable token metadata. Source fingerprints, distinct process IDs, workload hashes, raw acknowledgments, P50/P95 distributions and PostgreSQL resource samples are in [the raw report](reports/platform-benchmark.json).

| Worker processes | Mean jobs/s | Mean completion seconds | Sample SD seconds |
|---|---|---|---|
| 1 | 19.83 | 54.712 | 20.335 |
| 4 | 72.40 | 13.878 | 1.156 |
| 8 | 73.91 | 13.570 | 0.891 |
| 16 | 37.64 | 37.965 | 29.578 |

Four separate post-response/pre-ack crash probes recovered in **2.04–2.11 seconds** with a two-second lease. Each produced **two simulated external effects** for the crashed job and one accepted result. This is a controlled recovery measurement, not a production SLA.

The first 16-process variant had 22 retries versus eleven planned provider failures. Server logs confirm ten run-row lock statement timeouts; the full lock-holder cause remains unverified. All results recovered, but this is an important confounder. Shared-host variability and PostgreSQL history/cache effects remain. Do not turn the observed ratios into universal or live-Gemini performance claims. See [all repetitions, latency and resource measurements](docs/PLATFORM_BENCHMARK_REPORT.md) and [safe error-category evidence](reports/platform-postgres-errors.json).

Evidence-supported résumé wording: “Built a PostgreSQL-backed leased job queue with atomic claiming, idempotent submission and fenced results; tested independent-process contention, cancellation and crash recovery, and benchmarked 12,000 simulated jobs across 1/4/8/16 processes with latency and database resource measurements.”


## Claims still blocked or limited

- Public production deployment: authentication/TLS/ingress protection, provider quotas, backups/restore, HA and operational soak/outage verification remain required.
- Live Gemini: two successful smoke evaluations, four recorded responses, 418 input / 126 output tokens in accepted-result metadata. This is not a complete billing ledger or accuracy/throughput study. A live two-document RAG smoke passed with both sources retrieved and cited; ask before expanding paid testing.
- Human judge validation: all fifty user-supplied labels are complete (10 pass, 40 fail). Ten paired live predictions measured 60% agreement, with TP=2, TN=4, FP=4 and FN=0. All four disagreements involved instruction-injection responses.
- Hosted GitHub Actions: both workflows subsequently passed on `cb28a72`; artifact metadata is verified, artifact downloads are not. The diagnostic and RAG application revision `0b84e4d` also passed both hosted workflows.
- Historical 3.091× result: ratio of mean completion times for a simulated single-process 1-vs-configured-16-lane experiment; observed concurrent peak was five. It is not evidence of sixteen simultaneously active workers, caching or live-provider speedup.

See [prioritized engineering review](docs/PLATFORM_REVIEW.md) and [claims audit](docs/RESUME_CLAIMS_AUDIT.md).


## Controlled restore and labeling preparation

A real local pg_dump/pg_restore drill passed on generated fake work: completed results, pending jobs and submission idempotency survived restoration; the restored pending job then produced one accepted result. Temporary drill databases were removed. See [drill evidence](reports/backup-restore-drill.json) and deployment instructions. This does not prove host-loss/HA/PITR recovery, production RPO/RTO, offsite storage, encryption or a scheduled backup policy.

A deterministic shuffled human review packet without category hints and a separate blank label file are prepared locally. At that preparation milestone, zero labels were generated or supplied; human-judge accuracy remains unmeasured. See [human instructions](docs/HUMAN_LABELING.md).

The repeatable loopback fake-provider portfolio demo passed with four accepted results, submission replay and a stored-run comparison (`reports/portfolio-demo.json`). A separate 2,000-job local diagnostic capture did not reproduce the historical timeout (`reports/lock-followup-summary.json`); its different environment and single repetition do not establish a fix or new general speedup. The human review preparation record (`reports/human-review-preparation.json`) remains historical; all fifty user labels are now complete (`reports/human-labels-completion.json`); live RAG and public-release controls remain pending as described in `docs/NEXT_VALIDATION.md`.

Offline judge-collection follow-up: user decisions were validated and frozen without modification. `reports/judge_validation.json` remains BLOCKED with 50 labels and zero paired predictions. A bounded collector now preserves partial successes, usage and failure metadata without retries or evidence overwrite; it does not verify billing tier or provide a complete cost ledger. The user requested preparation only until free-tier status is confirmed. No new Gemini requests or human labels were generated.

## Live validation update

The ten-example live judge comparison is recorded in reports/judge_validation.json, with predictions and provenance hashes. It covers ten preselected examples from the controlled fifty-example set. The two-document live RAG run is recorded in reports/live-rag-smoke.json and passed Recall@2, Hit Rate@2 and inspected citation support for one answer. Earlier pending-status entries retain their original milestone scope.
