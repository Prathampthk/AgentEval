# Platform engineering review

Review baseline: commit `264f683e01518920b68709b8b1b7675a970e66f6`. This update preserves the evaluation/RAG/dashboard features and changes queue correctness, overload behavior, process verification and deployment. Production readiness is **not established**.

| Priority | Problem and consequence | Fix or remaining action | Principle |
|---|---|---|---|
| Critical, fixed | An UPDATE lease predicate could be evaluated before a row-lock wait; completion/failure could accept an expired claim | Lock the job first, then evaluate current ownership and database-clock expiry; regression tests cover completion/failure/renewal blocked past expiry | Check authority at the point of mutation |
| High, fixed | Capacity existed but API configuration and bounded admission contention handling were incomplete | Validated queue capacity; bounded lock wait; 429/503 with retry hints; duplicate replay works when full | Bound work at admission and expose overload |
| High, verified in controlled tests | Coroutine-only tests do not prove independent process behavior or the side-effect/acknowledgment boundary | Competing subprocess claims/submissions, stale/canceled worker, three abrupt crash points and fsynced fake effects | Test the failure boundary, not only happy-path return values |
| High, deployment improved | Runtime had no concrete restricted container deployment | One-shot migrations, non-superuser DML role, non-root/read-only runtime, separate databases, loopback API and pinned images | Separate administration from execution |
| High, remaining | The first 16-process benchmark recorded 22 retries for eleven injected failures; traces show ten extra finished evaluations without acknowledgment | All 1,000 results recovered; PostgreSQL logs confirm ten run-row lock SELECT timeouts. The prolonged lock-holder cause is unverified because benchmark INFO events were disabled. Add event capture and profile transaction/lock waits before production sizing; retain this confounded result | Recovery evidence does not replace failure diagnosis |
| High, remaining | No public authentication/TLS/ingress budget enforcement, backup-restore drill or HA validation | Add operational controls before public deployment; validate storage/backup failure modes | Local correctness is not operational readiness |
| Medium, explicit limit | Sixteen slots are process-local, not an installation/provider quota | Budget sum of all processes/API traffic; add a global provider limiter only if deploying paid distributed workloads | Distinguish resource scopes |
| Medium, benchmark corrected | Historical 3.091× was sometimes described as sixteen active workers | It is the ratio of mean completion times (40.401/13.070 s) for one process configured with 1 vs 16 async lanes; measured concurrent peak was **5** | Configuration is not observation |
| Medium, remaining | Direct SQL in routes and one large frontend component increase change surface | Extract cohesive services/components when relevant behavior changes justify it; no framework rewrite | Prefer measured simplification |
| Medium, remaining | Admission serialization, run-summary locks and historical storage can constrain scale | Keep correct transactions, measure contention, introduce retention/aggregation changes only with evidence | Optimize verified bottlenecks |
| Medium, remaining | RAG assembled context can exceed evaluation limit; broad timeout handler misclassifies some failures | Align context budgets and error categories in a separate existing-functionality fix | Preserve error meaning across boundaries |

## Historical benchmark review

The original six 1,000-job variants used the same logical cases, simulated provider waits, controlled retry injection, PostgreSQL queue and no response caching. There is no live Gemini throughput, token-cost or caching achievement. The 3.091 ratio is arithmetically valid for that report. Startup/admission were excluded; measured completion latency includes queue waiting. The shared host, database warm-up/history, scheduling, retry placement and fixed configuration order limit causal claims. Two audit reproductions are preserved under `reports/audit`: the quiet run reported 3.255×, while a run overlapping audit-tool installation reported 2.376× and is explicitly confounded. Neither supersedes the original raw report or establishes a universal speedup.

The new process sweep rotates order, records workload hashes and process IDs, includes PostgreSQL counters and optional container statistics, and separates crash-recovery probes. It still runs on shared infrastructure and is a simulation. See the new report for actual values and limits.

## Provider, human study and hosted CI

The Gemini adapter uses the official SDK, validated structured judgment and separately bounded connection/request/application timeouts. Controlled SDK-transport tests cover generation, judgment and embeddings. No securely bound Gemini key or model is currently available. A live sample still needs those bindings, allowed provider outbound access, model authorization/quota, a small explicit case count and usage/error review. Do not reuse a credential pasted into chat; rotate it and bind its replacement securely.

The prepared human study has 50 unlabeled rows, only ten distinct questions with five variants, a documented positive class and analysis tooling. Zero human labels means agreement/precision/recall/false-positive rates are unmeasured. Improve partial/ambiguous examples and avoid using category names as a label shortcut; freeze the rubric before collecting actual labels. No labels were generated by this review.

Local checks do not prove hosted GitHub Actions execution. Confirm the deterministic PostgreSQL and container jobs on GitHub, uploaded artifacts, fork credential isolation, optional live workflow permissions and runner resource limits. Workspace network policy prevented hosted-run API inspection during the earlier audit.

## Security and maintenance

SQL uses parameter binding; body sizes, schema lengths, provider/job/run deadlines, pool limits and retry budgets are bounded. Worker error logs retain safe exception categories/types, IDs and attempts rather than provider text or credentials. Runtime has no DDL/admin URL. Generated local credentials and database selectors remain ignored, and build contexts exclude local secrets. Pinned dependency audits performed during baseline review reported no known advisories at that time; this is not a security guarantee. Continue dependency/image scanning, secret rotation and safe error review. Administrator credentials in local test/benchmark services are intentionally limited to dedicated controlled databases; never expose them in an application deployment.

## Prioritized remaining work

1. Before public use: authentication/TLS/ingress and provider budgets, backup/restore exercise, resource sizing and hosted CI verification.
2. Diagnose prolonged run-row lock holds and extra 16-process retries with captured worker events and transaction/lock profiling. Server logs verify ten run-lock SELECT timeouts, but not the full causal chain; do not tune production from this outlier.
3. Correct existing RAG context/error-mapping issues; retain endpoint regression tests.
4. Validate live provider behavior with securely configured credentials and a small budget. Add a global limiter if multiple paid workers require one.
5. Operational soak/outage tests, retention policy, migration rollout/rollback and monitoring thresholds. Do not infer these from local process tests.
6. Optional maintainability: extract route services/frontend components incrementally; improve human-study diversity; optimize only measured contention.
