# Prioritized implementation plan

Milestones 1–5 and 7–10 are implemented and locally verified. Milestone 6 software and labeling materials are prepared, but the human study is BLOCKED on actual human labels and live-judge predictions. Milestone 11 review and demonstration documentation are complete for the local/simulated scope; live Gemini validation remains blocked on secure credentials/model. Work was committed and pushed in milestone increments; no results were fabricated.

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

Milestone 6 tooling increment: 50 unlabeled examples, a strict human-label template, optional judge runner and tested agreement analysis exist. The actual human study remains BLOCKED; independent RAG/regression/dashboard work continues without inventing labels.

Milestones 7–10 are implemented: pgvector RAG target, compatible-run regression checker/CI definitions, tested React dashboard, and completed 1,000-job simulated benchmark with three repetitions per configuration. Human-study measurements and live-provider checks remain external prerequisites, not fabricated completed milestones. Final security/architecture review is documented in FINAL_REVIEW.md.
