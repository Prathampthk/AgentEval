# Milestone 5 — reliability and run deadlines

This increment adds connection health checks (`pool_pre_ping`) and overall queued-run deadlines (default 900 seconds; API accepts 1–3600 seconds). Migration 0003 stores deadline_at; old runs with NULL deadlines retain their earlier semantics.

Claims, renewals and result acceptance reject expired runs using database time. Recovery cancels remaining active jobs with `run_timeout`, retaining earlier accepted results. Deadline outcomes must be treated as infrastructure-incomplete when comparing quality.

The dedicated database interruption test connects its control session to the PostgreSQL maintenance database, disables connections to the validated `*_test` database, terminates its existing backends, and observes heartbeat cancellation. It then restores connections and verifies automatic expired-lease recovery and one accepted result. Cleanup restores connections even if an assertion fails. Development and production databases are not targeted.

Validation: 86 tests passed, zero failures/errors/skips, including migration round-trips. Lint and formatting passed. These are controlled connection-outage tests, not evidence for every network partition or host/storage failure.
