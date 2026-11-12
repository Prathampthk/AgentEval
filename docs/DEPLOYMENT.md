# Container deployment

This is a controlled, local deployment. The API binds only `127.0.0.1:8011`; an optional single-owner access gate is available below. TLS termination, multi-user isolation, ingress limits, provider budgets, operational backup/restore and high availability must be supplied before public deployment. Passing simulated tests does not establish production readiness.

```bash
python scripts/compose_env.py
docker compose --env-file .local/compose.env build api tests
docker compose --env-file .local/compose.env up -d --wait api worker
python scripts/compose_smoke.py
docker compose --env-file .local/compose.env --profile verification run --rm tests
```

The credential generator preserves existing `.local/compose.env` and creates it with mode 0600. Never commit this file or print resolved Compose configuration. The initializer provisions a non-superuser runtime role. The one-shot migrator alone receives administrator credentials; API/worker have SELECT plus narrowly scoped INSERT/UPDATE and no DDL privileges. Runtime containers use non-root UID 10001, a read-only filesystem, a temporary `/tmp`, dropped capabilities and no-new-privileges. Source files are readable inside the image despite restrictive host umask. The database has no published port and persists in a named volume. Initializer scripts run only on a fresh volume; changing password variables does not rotate existing PostgreSQL roles. Preserve the volume during upgrades and plan migration/rollback and role rotation explicitly.

Images and dependency versions are pinned. Builds accept a public CA bundle through BuildKit secret `proxy_ca` (`AGENTEVAL_BUILD_CA`, default ignored `.local/build-ca.crt`, copied from the system bundle by the credential setup script); TLS verification stays enabled. Keeping the build-secret source inside the workspace avoids newer Bake filesystem-read entitlement failures without granting external filesystem access. Fake mode is deliberate and makes no billable calls. Live mode needs explicit provider configuration, credentials, trusted outbound TLS and budget controls; credentials must never enter an image.

`docker compose ... down` stops the stack without deleting its database volume. Never add `-v` to an operational teardown unless data deletion is intended. Stop old workers/API before schema-changing releases; mixed-version workers are unsupported.

## Optional single-owner access gate

Run `python scripts/create_access_token.py` to generate ignored `.local/access.env` with mode 0600. It preserves an existing file and never prints the token. To enable the gate on the local fake stack, use both env files and overlay consistently:

```bash
docker compose --env-file .local/compose.env --env-file .local/access.env -f compose.yaml -f compose.private.yaml up -d --wait api worker
```

Build the current API image first. In the browser, use username `owner` and the token value from your protected local file as the password. Do not paste it into chat, commit it, put it into a URL or print resolved Compose configuration. Command clients can use `curl --user owner http://127.0.0.1:8011/health/ready`, which prompts for the password. Existing smoke scripts target the unprotected fake demonstration by default; they do not automatically read owner credentials.

The gate protects API routes, schema/docs and dashboard assets before reading request bodies. Only `/health/live` remains unauthenticated, returning a static liveness response. Protected responses use `Cache-Control: no-store`; the authenticated readiness check works through the overlay. Invalid nonempty tokens fail application startup. Without `AGENTEVAL_ACCESS_TOKEN`, the legacy loopback demonstration remains open. Use only a trusted local configuration: removing the overlay/token disables protection. Rotate by replacing the token securely and restarting every API replica together; this credential has installation-wide owner access, no per-user roles or tenant isolation.

HTTP Basic is appropriate here only on loopback or behind trusted TLS ingress. The gate adds no public TLS, account lifecycle, brute-force protection, distributed provider quota or production certification. It never stores Gemini keys in browser code, and it does not authorize public hosting. Keep loopback binding and complete the separate release gaps before exposing a service.

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

The deterministic workflow uses real PostgreSQL without paid providers. The container workflow additionally builds both images, migrates, runs the HTTP smoke workflow with restricted runtime credentials, and executes the PostgreSQL suite. Both workflows passed at `da60690`; current job/step conclusions and artifact metadata are in `reports/hosted-ci-current.json`. Artifact contents were not downloaded. Future registry access, runner capacity, image builds and service DNS can still differ from this workspace. Optional live judge workflow is separate and must not expose credentials to untrusted forks.

The packaged Uvicorn command caps concurrent connections/tasks at 64 with backlog 128; the ASGI body limit is 32 KiB. These supplement the durable queue cap and four synchronous evaluation slots. Reverse-proxy connection/read timeouts and distributed rate/cost limits are still needed for public ingress. Configuration must be consistent across replicas.

## Controlled backup/restore drill

```bash
.venv/bin/python scripts/local_db.py admin .venv/bin/python scripts/backup_restore_drill.py
```

The local-only helper creates two uniquely named temporary databases in `agenteval-postgres`, migrates the source, inserts generated fake completed/pending work, takes a custom-format `pg_dump`, and restores it using `pg_restore --exit-on-error`. It verifies result identity, pending work, idempotency replay and execution after restoration, then drops only its drill databases. The dump is retained with mode 0600 under ignored `.local/backups`; the credential URL is never printed or passed on a command line. The script refuses non-local/non-test database configuration.

`reports/backup-restore-drill.json` records the actual successful controlled drill. This is an idle-source local snapshot exercise, not host-loss, corruption, PITR, HA or production RPO/RTO evidence. Production still needs encrypted offsite backups, scheduling, retention, access control and restoration exercises against the real deployment. Do not restore this generated test dump into an existing application database.
