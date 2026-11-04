# Lock contention investigation and hosted CI

No production queue policy, lease, retry, statement-timeout or acknowledgment behavior changed. The default remains four lanes in one Compose worker process, with a process-local cap. The investigation adds opt-in diagnostic capture; it does not establish a global provider quota or production readiness.

## Verified observations

Four final instrumented variants completed **4,000 jobs**: 1,000 identical logical cases at 4 and 16 independent single-lane processes, two repetitions each. Every variant had eleven deliberately injected provider retries, 1,000 accepted results, and zero captured SQL errors. No unexpected lease recovery or original ten-second statement timeout recurred.

| Processes | Rep | Seconds | Run-lock P95 ms | Run-lock P99 ms | Maximum run-lock call ms | Maximum sampled root transaction age s |
|---|---|---|---|---|---|---|
| 4 | 1 | 15.836 | 27.79 | 57.79 | 330.81 | 0.187 |
| 16 | 1 | 27.135 | 641.71 | 3322.97 | 5694.85 | 5.569 |
| 16 | 2 | 17.911 | 457.30 | 824.60 | 1518.06 | 1.545 |
| 4 | 2 | 17.839 | 23.26 | 51.67 | 1766.11 | 1.716 |

Run-row serialization is visible in the blocker graphs. More processes queue behind the same run summary lock. Sampled root blockers include client-read/idle-in-transaction states and WAL synchronization/write waits. These are observations, not proof of a particular CPU, storage or network root cause. Transaction age is not exact lock-holding duration, and a run-lock call includes scheduling/network/result decoding as well as lock waiting. Soft blockers ahead in a lock queue are excluded from the root-blocker summary.

The historical sixteen-process run had ten server-confirmed run-lock statement timeouts and extra attempts. This capture did **not** reproduce those timeouts, so the historical long lock-holder cause remains unresolved. It is not defensible to claim the slowdown fixed. Do not increase timeouts or redesign transactions just to improve a benchmark score.

## Implementation and verification

`--diagnostics` adds SQL operation categories, backend/process IDs, durations, SQLSTATE/error types, allowlisted worker events and sampled numeric blocker graphs. It never writes SQL text, bind parameters, provider content, arbitrary application names or credentials. Capture is off by default. A real PostgreSQL test holds a run lock, observes the actual blocker, and verifies the resulting statement-timeout attribution (SQLSTATE 57014). Redaction and joined-claim classification have regression assertions.

**Full local suite: 130 passed, zero failures/errors/skips**, one existing dependency warning. See [test record](../reports/diagnostic-verification.json). The final capture has matching source fingerprints, identical workload hashes and distinct process IDs. A preliminary capture was retained locally after discovering a diagnostic-only classification issue: joined job claims were incorrectly grouped with run locks. Corrected final captures are the committed evidence; no slow repetition was removed from them.

Commands:

```bash
.venv/bin/python scripts/local_db.py admin .venv/bin/python -m agenteval.platform_benchmark --jobs 1000 --repetitions 2 --workers 4 16 --diagnostics --skip-recovery --output artifacts/lock-diagnostics.json
.venv/bin/python scripts/summarize_lock_diagnostics.py --input artifacts/lock-diagnostics.json
```

[Summary](../reports/lock-diagnostics-summary.json) and [gzip raw capture](../reports/lock-diagnostics.json.gz) retain every final repetition. Diagnostic logging and sampling add overhead, so these measurements must remain separate from [the original performance report](PLATFORM_BENCHMARK_REPORT.md).

## Hosted CI

Both workflows passed on commit `cb28a72`: [deterministic checks](https://github.com/Prathampthk/AgentEval/actions/runs/41766710226) and [container deployment checks](https://github.com/Prathampthk/AgentEval/actions/runs/41766710274). The failed build was traced through hosted annotations to Bake refusing an out-of-workspace CA read. Copying the public CA into ignored local state fixed it; TLS verification remains enabled and the CA remains a build-secret mount.

Every hosted job step conclusion was checked through the public GitHub web UI because the API is forbidden by this environment. GitHub lists `test-results` and `platform-process-smoke` artifacts with digests; their contents were not downloaded. The Node action-runtime deprecation warnings remain maintenance work. The subsequent diagnostic and RAG source revision `0b84e4d` also passed both hosted workflows: runs 41768068596 and 41768068502, with every step conclusion checked. Artifact names/digests were observed; downloads remain unverified. See [hosted evidence](../reports/hosted-ci-verification.json).

## Next decisions

Keep the existing bounded default; do not claim sixteen processes are optimal. Before changing locking, reproduce a prolonged holder while capturing the graph and correlate root-backend waits with client event-loop lag and storage/fsync telemetry on controlled hardware. Consider reducing same-run write serialization only if that experiment establishes a concrete bottleneck and cancellation/aggregate invariants remain tested. The existing RAG context/error-mapping issues were corrected in the next follow-up; see RAG.md. Two live generation/judgment smoke evaluations are now recorded in `reports/live-gemini-smoke.json`; they do not validate embeddings/RAG or explain database lock contention. Human labeling and deployment safeguards remain separate work. Both hosted workflows also passed at `da60690`; current step/artifact metadata is in `reports/hosted-ci-current.json`.

## Local checkout follow-up — 2026-11-04

A separate Docker/Linux aarch64 capture completed 1,000 simulated jobs at each of 4 and 16 independent single-lane processes, one repetition each. Both variants recorded exactly eleven planned retries, all 1,000 accepted results and no captured SQL errors. Source fingerprints match this checkout. The compressed raw report retains both variants; its decompressed SHA-256 is recorded in [the summary](../reports/lock-followup-summary.json). This adds 2,000 diagnostic jobs; it does not replace or pool with the original benchmark or four-variant capture.

| Processes | Seconds | Run-lock P99 ms | Maximum run-lock call ms | Observed peak evaluations |
|---|---|---|---|---|
| 4 | 4.832 | 2.93 | 14.60 | 4 |
| 16 | 3.213 | 70.60 | 89.12 | 10 |

The 16-process capture sampled root blockers in client-read/idle-in-transaction, active and WALWrite states; maximum sampled root transaction age was 0.064 s. The 4-process sampler observed no blockers, which does not mean no locks waited. Environment: Python 3.12.16, PostgreSQL 17.11, Docker Linux aarch64, ten reported logical CPUs. The existing fake API/worker remained running against the separate application database; shared PostgreSQL resource use was not isolated. One repetition, different hardware and diagnostic overhead preclude a comparative performance conclusion.

Command used with the existing local Compose database:

```bash
docker compose --env-file .local/compose.env --profile benchmark run --rm --no-deps benchmark python -m agenteval.platform_benchmark --jobs 1000 --repetitions 1 --workers 4 16 --diagnostics --skip-recovery --output reports/lock-followup-raw.json
.venv/bin/python scripts/summarize_lock_diagnostics.py --input reports/lock-followup-raw.json --archive reports/lock-followup.json.gz --output reports/lock-followup-summary.json
```

The benchmark image must contain the checkout being measured; build it before a future run. The raw JSON was moved into ignored `artifacts/` after verifying the gzip round-trip and all source fingerprints. Do not overwrite committed reports for a new experiment; select new output/archive names.

The full container suite also passed the controlled PostgreSQL lock-graph/statement-timeout test ([current verification](../reports/current-verification.json)). That forced 1.5-second timeout validates attribution, not the cause of the historical spontaneous ten-second timeout. No queue policy, retry, lease or timeout was changed.

Next useful experiment: on the original environment or comparable controlled hardware, collect per-process event-loop scheduling lag and lock-acquired-to-transaction-end timing alongside the existing numeric backend graph and storage/fsync telemetry. Distinguish client stalls while holding the run lock from server commit waits. Use a controlled delayed holder as a positive control, retain failures and all repetitions, then repeat without induced delays. None of these extra telemetry correlations has been measured yet. The historical root cause remains **unresolved**; more process counts or a higher timeout would not resolve that gap.
