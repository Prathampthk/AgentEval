# Local portfolio demonstration

Use the simulated Compose stack on loopback. This demonstration creates a two-case dataset, two queued runs and four accepted fake results, verifies submission replay, and compares the equivalent completed runs. It makes no paid requests and creates no human labels. The accepted results show queue mechanics, not AI accuracy. [Observed demo evidence](../reports/portfolio-demo.json) records the successful local run.

## Prepare once

From the repository root, install Python dependencies with `bash scripts/install.sh`. With Docker running, follow [the container setup](DEPLOYMENT.md):

```bash
python3 scripts/compose_env.py
docker compose --env-file .local/compose.env build api tests
docker compose --env-file .local/compose.env up -d --wait api worker
```

The setup preserves existing credentials and database volume. Inspect existing services before replacing a running stack; stop old API/workers for schema-changing updates. Compose binds the API to `127.0.0.1:8011` and defaults to four lanes in one fake-provider worker. Do not print resolved configuration or expose the API publicly.

## Present in five minutes

1. Open `http://127.0.0.1:8011/dashboard/` and explain immutable dataset versions, queued work and the simulated-provider label.
2. Run `.venv/bin/python scripts/portfolio_demo.py`. It first requires readiness to identify a fake, simulated provider with a ready database, before creating work. It connects only to `127.0.0.1`, bypasses proxies and refuses HTTP redirects. Use `--port` if the Compose loopback port differs.
3. Read the printed evidence-file path. Each invocation chooses a fresh ignored JSON file; explicit `--output` refuses an existing file. Inspect its dataset/run IDs in the dashboard: two completed queued runs, two cases each. Repeated invocations reuse the equivalent immutable dataset and retain new runs without deleting history.
4. Explain that replaying each submission key returns the same run and that one accepted result does not promise one external call after a crash. The demo checks one attempt per job in this controlled run; crash/recovery evidence is separate.
5. Run `.venv/bin/python -m agenteval.regression --demo-gate` to show the deterministic simulated PASS path used by CI. Unit tests separately cover FAIL and INCONCLUSIVE policy outcomes. Equivalent fake runs in the recorded demo compare as PASS; that is not statistical accuracy evidence.
6. Show [human-study status](HUMAN_LABELING.md): fifty completed human labels, zero paired judge predictions and BLOCKED accuracy. Show the two-run, single-case [live smoke record](../reports/live-gemini-smoke.json) separately from simulated benchmark and demo results; it does not validate live RAG.

If readiness fails or the worker is absent, diagnose the local stack; do not switch to Gemini to make the demo pass. On a worker timeout the script leaves its persisted run intact for inspection. It does not cancel work, delete data, restart services, rotate credentials or expand any paid budget. The preflight depends on truthful server configuration; it is not a distributed spending control or protection against an operator changing configuration mid-run.

For the host-only API on port 8000, start one fake worker with `AGENTEVAL_WORKER_CONCURRENCY=4` using the README's local database workflow, then use `--port 8000`. Do not mix an older worker process with a replacement.

For failure/recovery, present committed controlled evidence or use dedicated tests against `_test`; do not terminate the development database. Historical benchmarks and the lock outlier remain in their original reports. See [next validation boundaries](NEXT_VALIDATION.md) for live RAG and deployment safeguards. No public deployment is part of this demonstration.
