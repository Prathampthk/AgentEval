# Milestone 9 — React dashboard

Implemented a React/TypeScript dashboard with overview metrics, dataset creation, durable submission, run history, job monitoring/cancellation, per-case question/reference/answer/judgment details, baseline comparison, and human-study status. No human labels are fabricated and simulated aggregates carry an explicit warning. Submission retries retain their idempotency key until acknowledged; React escapes provider text.

Validation: TypeScript production build passed. An initial Chromium/Playwright workflow created a dataset, queued work, inspected a stored simulated answer, compared stored runs and displayed the pending human study. A later production recheck exposed a dropdown timing issue; that issue was corrected before final verification below. Backend suite: 107 passed before the additional overview metadata. A screenshot is retained under ignored frontend/test-results/dashboard.png.

The frontend polls with one refresh in flight and aborts stale requests. Backend remains local/controlled and unauthenticated. UI tests make only fake-provider calls. Hosted frontend CI build is configured, but hosted execution is unverified.

Final correction verification: the saved dataset is inserted into the selector immediately, and the browser waits for a nonempty rendered selection. Production build passed; the complete Chromium workflow, including FastAPI-served production assets and simulated-aggregate warning, passed (1 test). This supersedes the earlier premature production-verification wording.
