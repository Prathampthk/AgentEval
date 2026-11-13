# Implementation plan and completion status

The eleven local portfolio milestones below are implemented with scoped evidence. Human judge labeling, live judge collection and genuine human RAG review are complete. The local demo requires no API key. This is completion of the controlled portfolio scope, not production certification.

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


The original milestone ordering is retained above as design intent. Current deliverable evidence is indexed in [DELIVERABLES.md](DELIVERABLES.md); remaining work and its prerequisites are in [PROJECT_COMPLETION.md](PROJECT_COMPLETION.md). Historical milestone reports retain their original measurements and status at collection time.

New work should remain a small verified increment. Routine checks use fake providers; new live collection needs a fresh explicit allowance. Private-server preparation is complete locally, while provisioning and remote operational acceptance require the owner's provider choice and approval. No generated decisions may be presented as human labels.
