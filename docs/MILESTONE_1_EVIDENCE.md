# Milestone 1 evidence

Observed on 2026-11-03 in the current cloud instance, Python 3.12.14, Linux.

| Check | Observed result |
|---|---|
| `bash scripts/install.sh` | Passed against exact dependency pins; repeat installation succeeded |
| `.venv/bin/python -m pip check` | No broken requirements |
| `.venv/bin/ruff check src tests scripts` | Passed |
| `.venv/bin/ruff format --check src tests scripts` | Nine files already formatted |
| `.venv/bin/pytest -q --junitxml=artifacts/tests.xml` | 35 passed, one test-client deprecation warning, 0.81 seconds |
| Uvicorn startup and `.venv/bin/python scripts/smoke.py` | Real loopback HTTP request returned expected simulated answer and pass result |

The XML report is generated locally and ignored by Git; CI is configured to upload its own report. Tests exercise input validation, request-size rejection, valid/low-quality outputs, missing usage, strict score ranges, answer-key field isolation, malformed provider output, API/transport error classification, generation/judge timeouts, startup configuration, process-local admission and capacity release on failure/cancellation. SDK contracts use controlled SDK response objects, not live requests.

The managed command sandbox blocked proxy access and local test execution. Dependency installation, API tests, and loopback smoke testing succeeded through approved commands outside that sandbox. TLS verification remained enabled. The initial sandbox test process was stopped.

The API was started on loopback for validation. Future tasks must start a new process; publication does not retain processes.

Not verified: live Gemini/model access, embeddings, PostgreSQL, durable execution, crash recovery, GitHub-hosted CI, judge accuracy, human agreement, throughput or monetary cost. No benchmark or reliability claim follows from unit-test duration.
