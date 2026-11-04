# Reliability testing

Tests run without live Gemini and use real PostgreSQL for transactional behavior. Expected behavior and current evidence:

| Scenario | Expected behavior | Evidence / observed result |
|---|---|---|
| Concurrent duplicate submission | One run and one job set | Five concurrent submits return one run ID |
| Conflicting submission key | Reject conflicting request | HTTP 409 and original submission retained |
| Concurrent queue admission | Stay within cap | At cap one, two competing submissions create one job |
| Two claimers, one job | Exactly one committed claim | Independent PostgreSQL sessions return one winner |
| Worker process exits after claim | Work remains RUNNING until recovery | Real subprocess exits abruptly with code 17; forced expired lease is recovered and replacement completes attempt two |
| Response received, not persisted | External work may repeat; one accepted result | Simulated interrupted persistence yields two provider calls and one stored result |
| Expired lease | Cannot renew; recover or fail at exhaustion | Controlled database-clock expiration tests pass |
| Stale worker writes/fails | Reject with no result overwrite | LostLease raised for old token after a replacement claim |
| Cancellation during execution | Invalidate lease; reject late result | Cancellation and heartbeat tests cancel the active task and preserve CANCELED |
| Transient rate-limit failure | Persist retry schedule and budget | Simulated 429 category retries then completes; direct tests verify future eligibility survives new queue instance |
| Permanent provider failure | Fail without retry | Invalid-output/authentication tests retain attempt count one |
| Retry exhaustion | Stop claiming; terminal FAILED | Two-attempt policy test and expired-last-lease test pass |
| Result transaction rejected | Roll back result and job transition together | Actual score constraint failure leaves RUNNING with no accepted result |
| Concurrent completions | Preserve both results and correct run aggregate | Two jobs complete concurrently; run has two results and COMPLETED |
| API/application restart | Accepted work survives new process state | Fresh API/DB instances process persisted submission; separate API and worker HTTP smoke passes |
| Malformed structured output and provider timeout | Distinguish infrastructure failure from poor answer | Existing provider-contract and application tests pass |

These are controlled failure-injection tests, not evidence that all production failure modes are covered. Crash tests deliberately move the lease expiration into the past rather than waiting 60 seconds. The post-response crash window is simulated by withholding persistence; the before-execution test uses a real abrupt process exit. No exactly-once external-call claim follows.

NOT VERIFIED: stopping/restarting PostgreSQL during an active worker attempt, network partitions, production shutdown/network partitions, system-wide concurrency limits, live Gemini failures, or sustained reliability at benchmark scale. These remain in the reliability roadmap.

Run `.venv/bin/python scripts/local_db.py admin .venv/bin/pytest -q --junitxml=artifacts/tests.xml`. Only a dedicated `*_test` database is permitted: tests truncate data and round-trip migrations. See MILESTONE_3_EVIDENCE.md for the current observed suite result.

## Milestone 4 additions

Controlled tests now verify a 16-active evaluation bound with 120 persisted jobs, bounded task growth, failure/timeout isolation, lane reuse after cancellation, successful two-job drain with unclaimed work retained, forced drain cancellation followed by lease recovery, and shutdown during a committed claim without provider execution. These add controlled shutdown-under-load evidence; they do not verify production network partitions or database restarts. See MILESTONE_4_EVIDENCE.md for the current 84-test suite; milestone 3 reports are historical.

## Independent process and post-lock verification

`tests/integration/test_process_guarantees.py` adds eleven real-PostgreSQL scenarios with independent Python interpreters, filesystem barriers and observed PostgreSQL lock waits:

| Scenario | Required observation |
|---|---|
| Three concurrent duplicate submissions | Same run ID, one job, three distinct process IDs |
| Two competing independent claimers | One successful claim |
| Recovered lease and stale old process | Old completion rejected, replacement can commit |
| Cancellation with blocked old process | Old completion rejected, canceled result absent |
| Crash before provider work | Replacement creates one result and one external effect |
| Crash after response/effect, before acknowledgment | Replacement creates one result and **two** external effects |
| Crash after commit, before caller acknowledgment | Committed result retained, no redelivery |
| Completion/failure/renewal blocked past expiry | Database-clock guard rejects after row lock is released |
| Capacity/lock overload | 429/503 retry hints; duplicate replay retains original run |

Crash tests use `os._exit(86)` and fsync the fake external side-effect record. Lease expiry for recovery assertions is advanced by controlled SQL; the benchmark recovery probe separately waits for a real two-second lease. These tests do not kill the host, corrupt WAL, or prove external-provider cancellation. Run them against the dedicated `_test` database; they truncate only that database and must not share it with another concurrent suite.

The fresh-volume container check exposed one initial connection-establishment timeout (126 tests passed, one setup error). The integration fixture now waits up to 30 seconds for a connection before a test starts, retrying only connection acquisition. It does not retry test transactions or operations, and runtime five-second connection/ten-second statement limits remain unchanged. Final rerun results are in `reports/platform-verification.json`; the initial failed run is disclosed there.
