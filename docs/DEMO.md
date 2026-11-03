# Local demonstration

1. Run `bash scripts/install.sh`, `npm ci --prefix frontend`, and `npm run build --prefix frontend`.
2. Run `.venv/bin/python scripts/local_db.py start` and `.venv/bin/python scripts/local_db.py admin .venv/bin/alembic upgrade head`.
3. Start the API from the repository root with `AGENTEVAL_PROVIDER=fake .venv/bin/python scripts/local_db.py run .venv/bin/uvicorn agenteval.api:app --host 127.0.0.1 --port 8000`.
4. In another terminal start `AGENTEVAL_WORKER_CONCURRENCY=16 AGENTEVAL_PROVIDER=fake .venv/bin/python scripts/local_db.py run .venv/bin/python -m agenteval.worker`.
5. Use the API's /dashboard/ page: create a dataset, submit work, inspect jobs/answers, compare completed runs, and inspect the honestly pending human study. Do not expose the service publicly.
6. Run `.venv/bin/python -m agenteval.regression --demo-gate` for the same deterministic quality gate used in CI.
7. Run `.venv/bin/python scripts/smoke_jobs.py submit` then `check` for a CLI submission-to-result demonstration.

For failure/recovery evidence use the dedicated tests; do not terminate a development database merely to demonstrate failure. Benchmark instructions and data are in BENCHMARK_METHODOLOGY.md and the benchmark report. Human-labeling instructions are in HUMAN_LABELING.md.
