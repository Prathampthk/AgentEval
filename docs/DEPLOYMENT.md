# Container deployment

This is a controlled, local deployment. The API binds only `127.0.0.1:8011`; authentication, TLS termination, ingress limits, provider budgets, backup/restore and high availability must be supplied before public deployment. Passing simulated tests does not establish production readiness.

```bash
python scripts/compose_env.py
docker compose --env-file .local/compose.env build api tests
docker compose --env-file .local/compose.env up -d --wait api worker
python scripts/compose_smoke.py
docker compose --env-file .local/compose.env --profile verification run --rm tests
```

The credential generator preserves existing `.local/compose.env` and creates it with mode 0600. Never commit this file or print resolved Compose configuration. The initializer provisions a non-superuser runtime role. The one-shot migrator alone receives administrator credentials; API/worker have SELECT plus narrowly scoped INSERT/UPDATE and no DDL privileges. Runtime containers use non-root UID 10001, a read-only filesystem, a temporary `/tmp`, dropped capabilities and no-new-privileges. Source files are readable inside the image despite restrictive host umask. The database has no published port and persists in a named volume. Initializer scripts run only on a fresh volume; changing password variables does not rotate existing PostgreSQL roles. Preserve the volume during upgrades and plan migration/rollback and role rotation explicitly.

Images and dependency versions are pinned. Builds accept a public CA bundle through BuildKit secret `proxy_ca` (`AGENTEVAL_BUILD_CA`, default system bundle); TLS verification stays enabled. Fake mode is deliberate and makes no billable calls. Live mode needs explicit provider configuration, credentials, trusted outbound TLS and budget controls; credentials must never enter an image.

`docker compose ... down` stops the stack without deleting its database volume. Never add `-v` to an operational teardown unless data deletion is intended. Stop old workers/API before schema-changing releases; mixed-version workers are unsupported.

## Reproducible process benchmark

```bash
docker compose --env-file .local/compose.env --profile benchmark run --rm benchmark
```

This uses a separate `agenteval_benchmark` database and writes `reports/platform-benchmark.json`. It runs 1,000 identical logical cases at 1, 4, 8 and 16 **independent processes**, one lane each, three rotated-order repetitions, plus one crash recovery probe per configuration. No process starts one task per pending job. Readiness barriers exclude interpreter startup and admission from the timed window. Do not run tests, builds or unrelated workload during measurement.

Host execution with the existing local database helper also records sampled Docker PostgreSQL CPU/memory/block I/O:

```bash
.venv/bin/python scripts/local_db.py admin .venv/bin/python -m agenteval.platform_benchmark --jobs 1000 --repetitions 3 --workers 1 4 8 16 --postgres-container agenteval-postgres --output reports/platform-benchmark.json
```

Docker statistics are optional container-wide samples, not isolated per-query accounting. The database counters are database-scoped. Container execution does not mount the Docker socket, so container CPU/memory samples are unavailable there; PostgreSQL counters remain available. The benchmark requires a database name ending `_benchmark` and refuses unfinished work. Failed experiments cancel their own runs and keep evidence. It never truncates the application database.

## Hosted checks

The deterministic workflow uses real PostgreSQL without paid providers. The container workflow additionally builds both images, migrates, runs the HTTP smoke workflow with restricted runtime credentials, and executes the PostgreSQL suite. These definitions still require a successful hosted run: registry access, runner capacity, image builds, service DNS and artifact permissions can differ from this workspace. Optional live judge workflow is separate and must not expose credentials to untrusted forks.

The packaged Uvicorn command caps concurrent connections/tasks at 64 with backlog 128; the ASGI body limit is 32 KiB. These supplement the durable queue cap and four synchronous evaluation slots. Reverse-proxy connection/read timeouts and distributed rate/cost limits are still needed for public ingress. Configuration must be consistent across replicas.
