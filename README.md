# AgentEval

A local AI evaluation and regression-testing platform with durable PostgreSQL jobs, bounded workers, a pgvector RAG target, regression checks and a React dashboard. Live evidence includes two Gemini evaluation smokes, a ten-example comparison with human labels, and a two-document RAG smoke.
**Core stack:** a local FastAPI evaluation workflow, PostgreSQL persistence, and a durable job queue with a configurable bounded worker pool. Gemini adapter contracts and a small live generation/judgment smoke sample are verified.

## Run locally

Requires Python 3.12+. From the repository root:

```bash
bash scripts/install.sh
.venv/bin/pytest -q
AGENTEVAL_PROVIDER=fake .venv/bin/uvicorn agenteval.api:app --host 127.0.0.1 --port 8000
```

In another terminal, from the same directory:

```bash
.venv/bin/python scripts/smoke.py
```

The stateless smoke test submits a question with `Paris` as supporting context, receives a simulated answer, and checks the result. This stateless path requires no API key, database or paid requests. Interactive API documentation is available at `/docs` on the running server.

`POST /evaluations` accepts dataset name/version, test case ID, question, expected answer, context, optional prompt and optional exact-match requirement. Each request generates an answer and judges it; results are returned directly and are not retained. Generation never receives the expected-answer field. On this stateless endpoint dataset versions remain caller-supplied labels. For persisted immutable versions, use the database workflow below.

The fake provider echoes context and uses a substring check. Its scores demonstrate the workflow only, not AI evaluation quality. Every result identifies its provider/model and whether it is simulated.

## Optional Gemini mode

On macOS or Linux with Python 3.12+ and Docker Compose running, launch the dashboard, PostgreSQL, and worker from a fresh checkout:

```bash
python3 scripts/run_gemini.py --model gemini-3.1-flash-lite
```

Choose a model available to your Gemini project. Enter your key at the hidden prompt or supply it through `GEMINI_API_KEY` in the environment. Open `http://127.0.0.1:8012/dashboard/`, create a dataset, and submit a queued run. The launcher uses a separate Compose project from the simulated demo. See [provider configuration](docs/PROVIDER_CONFIGURATION.md) for restart, shutdown, and provider usage details.

For a manual launch, supply `GEMINI_API_KEY` securely and set `AGENTEVAL_MODEL` and `AGENTEVAL_PROVIDER=gemini` before starting the API and worker. Do not commit secrets. The configured model is used for both generation and judgment, which can introduce shared-model bias. Each evaluation makes two requests, with SDK retries disabled. Token counts remain null when absent from provider metadata.

Local `gemini-3.1-flash-lite` completed one synchronous and one queued evaluation of the same simple case; see [live evidence](reports/live-gemini-smoke.json), committed in `da60690`. The judge uses `response_json_schema=Judgment.model_json_schema()` with two offline wire-contract checks. These two results establish connectivity and structured output only, not accuracy, throughput, embeddings or RAG quality. Accepted-result metadata totals 418 input and 126 output tokens across four generation/judgment responses; it excludes failed/discarded attempts and is not a billing ledger. Ask before expanding paid testing. Never enter keys in chat; fake mode remains the demonstration default.

## Checks

```bash
.venv/bin/ruff check src tests scripts migrations
.venv/bin/ruff format --check src tests scripts migrations
.venv/bin/pytest -q --junitxml=artifacts/tests.xml
.venv/bin/python -m pip check
```

GitHub Actions defines the same deterministic checks with an isolated PostgreSQL service and no live-provider credentials. Both hosted workflows passed on `0031224`; [judge-adoption hosted evidence](reports/hosted-ci-judge-adoption.json) records step conclusions and artifact metadata, with contents not downloaded. The deterministic workflow runs the PASS/FAIL/INCONCLUSIVE regression demonstration gate.

## Operating limits

Local/controlled demonstration only: an optional single-owner gate is available in [deployment instructions](docs/DEPLOYMENT.md#optional-single-owner-access-gate). Bind to loopback; do not expose this API publicly. Request bodies are capped at 32 KiB; fields have individual length limits. Each process admits at most four evaluations and rejects excess requests with HTTP 429. This is not a global worker limit or durable queue. Each provider operation has a 30-second application deadline; two sequential operations may take about 60 seconds. The SDK also receives a request timeout. Separate connection, job, lease and run deadlines belong to later work.

`/health/live` confirms API liveness. `/health/ready` reports provider configuration and checks migration readiness when PostgreSQL is configured; it does **not verify Gemini connectivity**. Provider failures produce sanitized HTTP 502 or 504 errors; poor answers produce normal evaluation results with `passed=false`. No automatic application retries are implemented. No request/answer/key content is deliberately logged by application events.

Start with [architecture](docs/ARCHITECTURE.md), [evaluation methodology](docs/EVALUATION_METHODOLOGY.md), [milestone evidence](docs/MILESTONE_1_EVIDENCE.md), and [the implementation plan](docs/IMPLEMENTATION_PLAN.md). No complete target résumé claim is verified; see [the audit](docs/RESUME_CLAIMS_AUDIT.md).

## Persist datasets and evaluation runs

Requires a working local Docker daemon. The helper uses the managed local socket, a digest-pinned PostgreSQL 17 image, loopback port 5432, protected random local credentials, and bind-mounted data under ignored `.local/`. It reuses its own labeled container and refuses unrelated name collisions. If port 5432 is in use, inspect the existing service; do not remove another project's database.

From the repository root:

```bash
.venv/bin/python scripts/local_db.py start
.venv/bin/python scripts/local_db.py admin .venv/bin/alembic upgrade head
AGENTEVAL_PROVIDER=fake .venv/bin/python scripts/local_db.py run .venv/bin/uvicorn agenteval.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
.venv/bin/python scripts/smoke_persistence.py create
.venv/bin/python scripts/smoke_persistence.py check
```

`create` saves a small versioned dataset and runs it. Stop and restart only your API process, then run `check` again to verify saved data remains readable. Do not use `create` with live Gemini: the fixture explicitly expects simulated results.

| Route | Behavior |
|---|---|
| `POST /datasets` | Save 1–20 cases atomically; HTTP 201 new, 200 equivalent existing, 409 conflicting name/version |
| `GET /datasets/{id}` | Retrieve the saved version and cases |
| `POST /runs` | Accept `dataset_id` and optional `prompt`; execute now and persist COMPLETED or FAILED; HTTP 201 means run created, not quality passed |
| `GET /runs/{id}` | Retrieve configuration, state, results and sanitized failure category |
| `GET /runs?dataset_id=...&limit=20` | List recent runs for a dataset; limit 1–100 |

Case fields are `external_id`, `question`, `expected_answer`, optional `context` and `exact_match`. The existing body-size cap still applies to the entire dataset. A provider failure records FAILED with no partial results. Successful evaluations can still contain `passed=false` answers. Database errors return sanitized HTTP 503 responses; record lookup errors return 404.

The original `/runs` endpoint remains request-scoped: up to 20 cases execute sequentially per run, sharing the four-active-request limit with stateless evaluations. Each case can make two paid calls in Gemini mode. Repeated POST /runs creates new work; there is no run-submission idempotency yet. A crash or database outage can leave a RUNNING row. No recovery is claimed.

Run all tests, including real-database tests:

```bash
.venv/bin/python scripts/local_db.py admin .venv/bin/pytest -q --junitxml=artifacts/tests.xml
```

Without `AGENTEVAL_TEST_DATABASE_URL`, integration tests are explicitly skipped. The test URL must name a dedicated database ending in `_test`: tests truncate its project tables and test migration downgrade/upgrade. Never point it at development or production data. Unit-only checks can use `.venv/bin/pytest -q -m 'not integration'`.

For external PostgreSQL, securely set `AGENTEVAL_DATABASE_URL` (`postgresql+asyncpg://...`); use a schema-owning `AGENTEVAL_MIGRATION_DATABASE_URL` when runtime has only DML permissions. Run migrations explicitly with `.venv/bin/alembic upgrade head`. Never commit these URLs. The helper's `run` mode injects only local runtime configuration; `admin` additionally injects local migration/test URLs. Existing explicit external URLs are preserved. Local configuration is not production secret management.

See [database schema](docs/DATABASE_SCHEMA.md), [milestone 2 evidence](docs/MILESTONE_2_EVIDENCE.md), and [engineering decisions](docs/ENGINEERING_DECISIONS.md). PostgreSQL startup and application processes must be restored explicitly in future tasks; a controlled generated-data dump/restore drill is recorded in [restore evidence](reports/backup-restore-drill.json), without production recovery guarantees.

## Durable queued runs

After installing dependencies and applying migrations, keep the API running and open another terminal:

```bash
AGENTEVAL_PROVIDER=fake .venv/bin/python scripts/local_db.py run .venv/bin/python -m agenteval.worker
```

The worker is a separate process and does not serve HTTP. By default it executes one evaluation at a time; a fixed pool can run up to 16. It renews leases, retries classified transient failures, and recovers expired claims. More worker processes can claim safely, but there is no global provider concurrency cap; use one process for the initial demonstration.

For a complete local smoke test, submit before starting the worker, start it using the command above, then check:

```bash
.venv/bin/python scripts/smoke_jobs.py submit
# Start the worker in another terminal, then:
.venv/bin/python scripts/smoke_jobs.py check
```

| Route | Behavior |
|---|---|
| `POST /queued-runs` | Dataset ID and optional prompt; required `Idempotency-Key` header; HTTP 202 and persisted run ID |
| `GET /runs/{id}/jobs` | Job states, attempts, retry eligibility, lease expiration and sanitized failure categories |
| `POST /runs/{id}/cancel` | Cancel active queued jobs; terminal runs remain unchanged; synchronous runs return 409 |

Equivalent queued submissions with the same key return the original run. Conflicts return 409. Keys are installation-wide with no expiry. A transactionally checked cap of 1,000 active jobs rejects overload with 429. Queue submission creates no provider calls itself. Run `execution_mode` distinguishes `sync` and `queued`; RUNNING queued runs may have only PENDING jobs, so inspect the job endpoint for progress.

Queued runs retain successful case results even if other jobs fail or the run is canceled. Result writes are fenced by lease token and expiration. A crash after receiving an external response can repeat a paid request; no exactly-once provider execution is promised. The three-attempt default limits automatic retries, not manual submissions with new keys. Live Gemini can cost up to two provider calls per attempt, and API/worker must use matching provider/model configurations.

Read [execution semantics](docs/JOB_EXECUTION_SEMANTICS.md), [reliability checks](docs/RELIABILITY_TESTING.md), and [milestone 3 evidence](docs/MILESTONE_3_EVIDENCE.md). The bounded pool and controlled drain/cancellation tests are implemented; controlled database-outage tests and performance benchmarks are documented in the later milestone evidence.

## Configure worker concurrency

For the fake-provider demonstration, start one worker with:

```bash
AGENTEVAL_WORKER_CONCURRENCY=16 AGENTEVAL_PROVIDER=fake .venv/bin/python scripts/local_db.py run .venv/bin/python -m agenteval.worker
```

Do not start this alongside an older worker merely to change its configuration. Stop only the worker process you started, then launch its replacement. The default is 1; accepted values are integers 1–16. Invalid values fail startup. Live-provider concurrency should be chosen against an agreed budget and rate limits.

A worker creates a fixed number of consumer loops; each claims only when ready to execute. The database queue can contain 1,000 active jobs without scheduling one task per job. Provider generation and judgment are sequential within each evaluation, so at most one provider operation per active evaluation is in flight. The five-connection PostgreSQL pool is independent of this setting. API request-based evaluations retain their separate four-active-request limit.

The concurrency cap is **per process**, not installation-wide. Multiple workers, or simultaneous synchronous API evaluations, can exceed 16 combined. To test the intended 16-active limit, use one worker configured to 16 and no competing synchronous evaluation traffic. This does not promise a particular throughput improvement.

SIGTERM/SIGINT stops new loop iterations and uses one shared 50-second drain window for all lanes. Remaining tasks are then canceled; unfinished jobs keep their leases and recover after expiration. A claim already in flight can commit during shutdown, but starts no new provider work after observing the stop signal. Provider cancellation is cooperative and can still incur charges.

Pool start/stop events report configuration and measured process-local active/peak evaluation counts. Counts cover actual evaluation execution, not pending jobs or final database writes; they are not a cost ledger. See [milestone 4 evidence](docs/MILESTONE_4_EVIDENCE.md) for the 120-job correctness test. The completed historical 1,000-job async-lane benchmark and new process sweep are documented below.

## Overall run deadline and reliability

Queued submissions accept `run_timeout_seconds` (default 900; 1–3600). Expired runs reject new claims and late results, then recovery marks unfinished jobs canceled with `run_timeout`. Earlier results remain available; quality comparison must regard incomplete coverage as inconclusive. Migration 0003 preserves NULL deadlines on old runs. Stop/restart old API and worker processes when applying schema-changing releases.

The isolated PostgreSQL tests now include disabling test-database connections, terminating its backends, and restoring access while a worker is active. Never run these tests against a development database. See [milestone 5 evidence](docs/MILESTONE_5_EVIDENCE.md).

## RAG target

The default database image now includes pgvector; apply migration 0004 with the administrative migration command. Use POST /documents with `title` and plain-text `content`, then POST /rag/ask with `question` and optional `k`. POST /rag/evaluate also accepts `expected_answer` and `expected_document_ids` and returns Recall@K, Hit Rate@K and answer evaluation. Source document/chunk IDs accompany retrieval results.

Fake embeddings are deterministic word hashes, explicitly simulated; Gemini embedding contracts are tested but live embeddings have not run. See [RAG methodology](docs/RAG.md). Existing SQL data was preserved during the local container image change.

## Regression checks

POST /comparisons compares stored baseline/candidate run IDs. GET /runs/{id}/comparison-input exports normalized artifacts. The same local/CI checker supports PASS (exit 0), FAIL (exit 1) and INCONCLUSIVE (exit 2):

```
.venv/bin/python -m agenteval.regression --demo-gate
.venv/bin/python -m agenteval.regression --baseline baseline.json --candidate candidate.json
```

Routine CI requires no paid API. See [regression policy](docs/REGRESSION_POLICY.md) for compatibility, thresholds, and the optional manual live sample.

## Dashboard

Requires Node 24. From the repository root:

```
npm ci --prefix frontend
npm run build --prefix frontend
```

Restart the API after building; it serves the dashboard at its `/dashboard/` path. For frontend development, `npm run dev --prefix frontend` proxies API calls to the local API. Do not expose the unauthenticated demonstration publicly.

Run `npm run format:check --prefix frontend` and `npm run build --prefix frontend` for the frontend checks. With the simulated Compose API and worker running, `AGENTEVAL_E2E_URL=http://127.0.0.1:8011 npm run test:e2e --prefix frontend` exercises the packaged dashboard through queued completion. With no target URL, the test starts its own development API and Vite server. Install Playwright Chromium or set `AGENTEVAL_E2E_BROWSER` to an installed Chromium executable. The test verifies the simulated provider before creating its browser-smoke dataset.

## Measured simulated performance

The committed 1,000-job benchmark compares concurrency 1 and 16 across three repetitions through the actual PostgreSQL queue. Mean completion times were 40.40 s and 13.07 s respectively: **3.09×** ratio of mean times, with all 6,000 accepted evaluations completed and 11 injected retries per variant. This is simulated-provider throughput, not live Gemini throughput; caching is disabled. Configured concurrency was 16, while observed peak overlap was five. The new independent-process sweep is reported separately.

See [benchmark methodology](docs/BENCHMARK_METHODOLOGY.md), [measured report](docs/BENCHMARK_REPORT.md), and raw `reports/benchmark.json`. Run only in the separate `_benchmark` database using the documented command.

## Complete environment setup

`bash scripts/setup_environment.sh` installs the pinned Python and frontend dependencies, builds the dashboard, starts the owned local pgvector database (unless an external app URL is configured), and applies migrations. Read [the demonstration steps](docs/DEMO.md) and [final review](docs/FINAL_REVIEW.md). Processes still need explicit startup; setup does not publish the environment.

Human review is complete: 50 labels were supplied, and the ten-example live Gemini sample measured 60% agreement, with four false positives and zero false negatives. Further paid calls require a budget review; the two recorded smoke evaluations do not establish the remaining allowance because failed/discarded requests are outside accepted-result usage. The dashboard report covers all fifty candidate-v2 pairs: ten development and forty response-level validation responses, with overlapping underlying questions.

## Fault-tolerant platform verification

See [container deployment and verification](docs/DEPLOYMENT.md), [delivery semantics](docs/JOB_EXECUTION_SEMANTICS.md) and [résumé evidence](RESUME_EVIDENCE.md) for the current backend upgrade. The new process sweep benchmarks **1, 4, 8 and 16 independent processes**, separately from the historical 1-vs-16 async-lane report above. Active queues have configurable capacity and retry hints; worker execution has fixed per-process bounds. Compose defaults to simulated providers and a loopback-only API. External side effects may repeat after crashes; no exactly-once external execution or public production-readiness claim is made.


Latest follow-up: [lock contention investigation and hosted CI](docs/LOCK_CONTENTION_REVIEW.md). The latest non-root container suite passed 195 tests ([verification](reports/private-server-verification.json)). Both hosted workflows passed at `0031224`; earlier Bake recovery evidence is retained. The historical lock-timeout outlier remains unresolved; optional diagnostic capture is now available without changing default queue execution.

Repeatable fake-provider portfolio walkthrough: [demo steps](docs/DEMO.md), `.venv/bin/python scripts/portfolio_demo.py`. All 50 human labels are complete, with fifty paired candidate-v2 predictions; [separate validation plans](docs/NEXT_VALIDATION.md) cover live RAG and deployment safeguards without authorizing paid calls or public release.

Prepare the next RAG study offline with `.venv/bin/python scripts/prepare_rag_study.py`. It freezes a six-document/eight-question synthetic fixture and leaves every human-review decision blank. See [study preparation](docs/RAG.md#broader-offline-study-preparation) before collecting answers; no live calls are made by this command.

Gemini free-tier preparation and bring-your-own-key configuration: [provider configuration](docs/PROVIDER_CONFIGURATION.md). Collection now preserves partial results and usage, refuses existing outputs, and caps live samples at ten calls. Free-tier eligibility and remaining quota must be checked in the provider project before expanding live testing.

Latest live validation: [judge comparison](reports/judge_validation.json) and [RAG smoke](reports/live-rag-smoke.json). The RAG run retrieved and cited both fixture documents, with Recall@2 and Hit Rate@2 of 1.0. All four historical v1 disagreements involved instruction-injection responses; candidate-v2 matched all fifty development/response-validation decisions.


The candidate-v2 judge prompt matched all ten human labels on the same development sample, correcting the four baseline instruction-injection false positives. The response-level holdout subsequently matched 10/10 labels. New Gemini processes use candidate-v2 by default and persist prompt provenance for compatible comparisons. See [prompt comparison](reports/judge-prompt-comparison.json).

The separately authorized [eight-question live RAG study](reports/live-rag-study-v1-summary.json) completed 28 attempted operations. All six answerable queries retrieved their expected documents at K=3; answer/citation/abstention review is pending. No further provider requests are authorized by that completed run.

RAG human review currently has zero of eight completed entries. The [offline validator](scripts/summarize_rag_review.py) checks frozen evidence, attribution and strict decisions without filling labels. Follow [review instructions](docs/RAG.md#complete-and-validate-human-review); missing reviews remain pending with null rates.

Optional local [single-owner authentication](docs/DEPLOYMENT.md#optional-single-owner-access-gate) now protects API/docs/dashboard routes. The repeatable [lock reproduction bundle](docs/LOCK_CONTENTION_REVIEW.md#repeatable-positive-control-and-recurrence-bundle) retained four 1,000-job uninjected variants and its positive control; the historical timeout cause remains unresolved. The [predeclared remaining judge requests](reports/judge-remaining-validation-plan.json) were subsequently completed under a separate 30-request allowance; [completion provenance](reports/judge-completion-provenance.json) retains the actual counts and usage.

Private single-owner server preparation is in the [server runbook](docs/PRIVATE_SERVER.md): loopback-only TLS through SSH, owner authentication, encrypted local snapshots with isolated restore checks, and optional health/backup timers. This profile is simulated-only until shared live-request controls are configured. It has been verified locally, with no remote deployment.
