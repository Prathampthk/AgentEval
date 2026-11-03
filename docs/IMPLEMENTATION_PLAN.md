# Prioritized implementation plan

Milestone 1 is implemented and locally validated; live Gemini access remains unverified. Milestone 2 now adds locally verified PostgreSQL persistence and migrations; milestone 3 now adds tested durable jobs and a sequential worker; milestone 4 now adds a verified bounded worker pool and controlled shutdown; milestone 5 now verifies controlled database interruption and overall deadlines; human-study data remains pending in milestone 6. Complete each with tests and matching documentation before advancing. Do not generate the whole project in one step.

| Priority | Milestone | Exit evidence |
|---|---|---|
| 0 | Audit and proposed architecture | Empty-repository audit, design and risks documented; user approves first implementation increment |
| 1 | Core evaluation vertical slice | Local FastAPI request works with fake provider; structured validation and error tests pass; Gemini adapter contract tested |
| 2 | PostgreSQL persistence | Alembic upgrades on a fresh real database; dataset/run/result lifecycle integration tests pass |
| 3 | Durable jobs | Transactional submission, unique idempotency, atomic claims, leases and guarded persistence tested |
| 4 | Bounded execution | Fixed pool, backpressure, deadlines, persisted retries and shutdown tested; overlap and maximum active bound measured |
| 5 | Reliability | Crash windows, recovery, cancellation, database interruption and stale-worker writes tested; evidence recorded |
| 6 | Judge validation | Rubric agreed; human supplies actual labels; confusion matrix and disagreement analysis generated with actual sample size |
| 7 | RAG target | Controlled documents, Gemini embeddings, pgvector retrieval and source tracking; known-reference retrieval tests |
| 8 | Regression CI | Compatible-run PASS/FAIL/INCONCLUSIVE policy; local deterministic command matches GitHub Actions; artifacts uploaded |
| 9 | React dashboard | Run monitoring, results, comparisons and actual judge validation displayed; API error states handled |
| 10 | Performance | Equivalent 1,000-job simulated runs at concurrency 1 and 16; repeated raw measurements and honest analysis; cache experiment only if justified |
| 11 | Final review | Security/architecture review, demonstration, limitations, evidence-linked résumé audit |

During milestone 1, add dependency configuration, local install/run commands, deterministic CI checks and a README. Prepare and verify the cloud environment against those actual commands, then save tested install/start instructions. Use the existing isolated checkout; no worktree is needed. PostgreSQL setup begins when persistence is implemented. Live Gemini checks require a selected model and securely configured credentials; routine tests must not require paid calls.

For each milestone, explain problem, alternatives, decision, implementation, verification, trade-offs and learning takeaway. Seek approval before major architectural changes. Keep implementation work reviewable and the application working at each completed stage.
