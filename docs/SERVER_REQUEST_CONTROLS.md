# Private single-host provider request controls

The private server now has an opt-in persistent SDK admission ledger in the shared `provider-budget` Docker volume, at `/budgets/provider.sqlite3`. All private API/worker replicas on **one Docker host** use this same file. A configured policy is required before a non-simulated provider can start. The default server profile stays fake; no key, paid request, provisioning or live deployment is authorized by this feature or its examples.

## What is enforced

Before each generation, judgment or embedding SDK call, one atomic SQLite transaction checks the total attempt ceiling, starts in the previous sixty seconds, and active/uncertain reservations. It reserves an attempt before dispatch. Independent API/worker processes therefore share the same counters and admission-concurrency limit. Exhaustion never resets on an API/worker restart, a request failure or key change. No response-cache or exactly-once external execution guarantee is implied.

Denied admission makes no SDK call and spends no attempt. An admitted failure still spends its attempt. A successful returned generation/judgment records available usage even if later application processing fails; embedding/failed/uncertain usage can remain unknown. No prompts, answers, API keys or raw exception messages are written to the ledger. It is an attempt ledger, **not a monetary spending cap or proof of free-tier eligibility**. SDK retries remain disabled.

One ordinary evaluation needs generation plus judgment (two admissions); a scored RAG query also needs a query embedding (three), and ingestion needs one embedding per chunk. Request policies count these operations, not HTTP submissions or successful evaluations. Select the rate accordingly rather than assuming one request per question.

Admission failures return HTTP 429 (`provider_budget_exhausted`, `provider_rate_limited`, or `provider_capacity`), with `Retry-After` for temporary rate/capacity rejection. An unavailable ledger returns HTTP 503 and prevents provider dispatch. A workflow can exhaust its allowance between generation and judgment; already admitted work may still incur charges without an accepted result. Queue retries also consume the shared allowance whenever they reach the SDK.

Cancellation, timeout, network failure, server-unavailable errors and process loss retain uncertain reservations. They do not expire automatically. This deliberately blocks new admission when an external outcome is uncertain. Definitive failures can release the slot but never refund the spent attempt. The limit governs SDK admission; it cannot prove a remote provider stopped processing after a lost response.

## Configure only after a fresh explicit allowance

On the approved server, with the current image built and the private profile still fake, set `APPROVED_TOTAL` and `APPROVED_RPM` to the numeric policy you have actually approved. Do not infer these from a free-tier label or reuse an earlier completed experiment's allowance. Then run:

```bash
docker compose -p agenteval-private --env-file .local/compose.env --env-file .local/access.env -f compose.yaml -f compose.private.yaml -f compose.server.yaml run --rm --no-deps api python -m agenteval.server_budget configure --max-attempts "$APPROVED_TOTAL" --requests-per-minute "$APPROVED_RPM" --concurrency 1
```

The total ceiling is cumulative, not a refill amount. Increasing an existing ceiling from 30 to 50 permits at most twenty further reservations if thirty have already been spent. Policy changes preserve history and are refused while active/uncertain reservations exist or when a proposed ceiling is below already spent attempts. Only trusted host operators can configure it; there is no public budget-reset endpoint. Configuration itself makes no SDK call.

Use the same Compose command with `exec -T api python -m agenteval.server_budget status` for counters, or `inspect-active` for active/uncertain IDs. Do not delete the ledger, change its path, rename its project volume, or recreate the volume to refill an allowance. A missing, unreadable or unconfigured ledger blocks private live startup. The shared path must remain on a supported local filesystem with mode 0600 and a protected parent directory; do not use NFS or claim this is a multi-host quota service.

## Live activation remains a separate operator action

Only after provider/host/deployment approval, a fresh allowance, and secure key/model configuration, append `-f compose.server-live.yaml` after all three private server files when recreating API/worker. That overlay requires model and key values through the environment; no real values belong in tracked files or command-line arguments. Review queued jobs and model/prompt compatibility before activation. The owner gate and loopback-only TLS remain in place. No live activation has been performed as part of this implementation.

The read-only private-server checker can monitor either provider without invoking it. Its default mutating demonstration refuses live providers. Existing non-private local Gemini profiles remain separate and are not governed by this private-server volume. This is not an account-wide limit covering outside tools or other installations using the same key.

## Reconcile uncertain reservations conservatively

Stop **all** API/worker replicas and any other clients using this ledger. Review provider-side usage and wait for/reconcile outstanding operations; a local crash does not establish remote completion. Inspect the specific reservation IDs. The CLI `reconcile --attempt ID --confirm-workers-stopped --confirm-provider-usage-reviewed` closes only the named uncertain reservations and leaves their attempts spent. Run it through a one-shot private-profile container while services remain stopped. The confirmation flags are operator attestations, not independent proof that a remote request has finished. Never run it automatically on a timer or claim it prevents duplicate external execution.

## Backups and recovery

The backup helper snapshots and encrypts this ledger while application writers are stopped, alongside the separate encrypted PostgreSQL dump. The backup's ledger is retained as **minimum known history**, not automatically restored. Rolling back the ledger can erase post-snapshot attempts and incorrectly grant more calls. After host loss, keep live execution disabled until external usage, post-snapshot uncertainty, policy and keys are reconciled. Keep application backup files and key escrow separate. A status counter is not a complete billing ledger.

Offline verification uses synthetic providers, independent processes, simulated process loss, strict admission ceilings, API rejection checks and encrypted snapshot round trips. It does not validate a live provider's quota windows, charges or throughput. The host clock must be trustworthy for the rolling-minute control; the persistent attempt ceiling does not rely on the clock.

## Damaged policy handling

Policy types and bounded integer ranges are checked on every admission and status read, not just at startup. A deleted, fractional, nonnumeric or out-of-range policy returns `provider_budget_unavailable` before dispatch; no new reservation is spent. This covers accidental corruption/manual edits, not protection against a privileged operator deliberately replacing the whole ledger.

Read-only `inspect-active` remains available if the policy row is missing but the attempt table is intact. After stopping all clients and reviewing provider-side uncertainty, explicit reconciliation can close the named reservations without refunding their spent attempts. If the policy remains invalid, the CLI reports `policy_status: unavailable`; live dispatch is still blocked. Configure a new explicitly approved valid total only after reconciliation. This repair path preserves attempt history and never automatically recreates an allowance or claims remote execution has ceased.
