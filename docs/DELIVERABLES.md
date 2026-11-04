# Deliverable status

Latest platform evidence: [engineering review](PLATFORM_REVIEW.md), [verification record](../reports/platform-verification.json), [résumé evidence](../RESUME_EVIDENCE.md). Production readiness and hosted CI remain unverified; the 16-process benchmark lock-timeout outlier needs further diagnosis.

| Deliverable | Status | Evidence |
|---|---|---|
| Backend and evaluation engine | VERIFIED locally with simulation | 127 passing backend tests; domain/service/API |
| PostgreSQL migrations and persistence | VERIFIED | Migrations 0001–0004; real PostgreSQL integration tests |
| Durable worker / idempotency / leases / recovery | VERIFIED in controlled scenarios | JOB_EXECUTION_SEMANTICS.md; RELIABILITY_TESTING.md |
| Bounded concurrency | VERIFIED process-local | 16 active evaluations, bounded tasks, cancellation/drain tests |
| Gemini generation/judgment/embeddings adapter | CONTRACT TESTED; live BLOCKED | SDK tests; no secure key/model binding active |
| RAG target | VERIFIED with simulated embeddings | pgvector ingestion/retrieval/HTTP tests; RAG.md |
| Regression checker | VERIFIED locally | PASS/FAIL/INCONCLUSIVE tests and deterministic demo gate |
| GitHub Actions | CONFIGURED; hosted run unverified | Deterministic tests/build/gate; optional budget-capped manual live workflow |
| React dashboard | VERIFIED core Chromium flow | Production build, dataset/run/details/comparison/study browser test |
| Automated suite | VERIFIED | 127 backend tests on host and container plus 1 browser workflow |
| Reliability evidence | VERIFIED, scoped | Real process exit, database connection interruption, fencing, rollback, cancellation and shutdown |
| Benchmark runner and report | VERIFIED simulated | 12,000 accepted process-sweep jobs; 1,000 per variant, 3 repetitions at 1/4/8/16 processes; PLATFORM_BENCHMARK_REPORT.md. Historical async-lane report retained separately |
| Human-vs-AI judge report | BLOCKED on actual labels and live predictions | 50 unlabeled examples; report explicitly BLOCKED and accuracy null |
| Architecture / decisions / demo | DOCUMENTED | ARCHITECTURE.md, ENGINEERING_DECISIONS.md, DEMO.md |
| Résumé audit | UPDATED with evidence boundaries | RESUME_CLAIMS_AUDIT.md; no exactly-once/live-quality claims |

Remaining outside action: securely enter a replacement GEMINI_API_KEY and a supported AGENTEVAL_MODEL in cloud environment settings, and supply actual reviewed human labels. The authorized live budget is at most 10 evaluations; zero live calls have been executed in this work. A full 50-example live study requires its own budget decision. Do not populate human labels with generated answers.
