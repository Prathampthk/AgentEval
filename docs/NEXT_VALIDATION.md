# Separate validation boundaries

The two completed Gemini smoke evaluations validate a narrow generation/judgment path. They are not evidence for semantic retrieval, human agreement or deployment safety. No paid calls or public deployment are authorized by this plan.

## Human review

The user completed all 50 labels under ignored `artifacts/`; validation found 10 pass and 40 fail. Decisions are frozen locally with a committed provenance hash (`reports/human-labels-completion.json`). Instructions and strict rubric are in [HUMAN_LABELING.md](HUMAN_LABELING.md). The historical v1 baseline measured 60% agreement on ten pairs, with four false positives on instruction-injection responses. Candidate-v2 subsequently matched all twenty reviewed decisions across ten development responses and ten response-level holdout responses. A human should review without AI predictions/category hints, supply their own identifier and keep ambiguity notes. The completed labels have been frozen before new predictions. Fifty variants of ten questions are a convenience sample, so later agreement must disclose that dependency and scope. Never replace unreviewed nulls with generated labels.

## Live RAG assessment

A live RAG smoke passed for two one-chunk documents and one query. First agree a hard incremental request/spend ceiling and check provider-side usage, including earlier failed or discarded calls. The later recorded RAG smoke in `reports/live-rag-smoke.json` reports 790 input and 161 output tokens across generation and judgment; embedding usage was not returned. This cannot establish total spend or the unused portion of an earlier allowance. Do not dispatch the optional hosted live workflow merely because its boolean input exists.

The [two-document smoke command](RAG.md#two-document-smoke-test) now runs through the local Compose API and records its evidence. Its simulated rehearsal passed. The completed live path used the fixture designed for five provider operations, including three embeddings, one generation request and one judgment call. Account for attempted requests when investigating any failure.

Broader study preparation is now available without provider access: `.venv/bin/python scripts/prepare_rag_study.py`. The six-document/eight-question fixture, frozen plan and empty review sheet are described in [RAG study preparation](RAG.md#broader-offline-study-preparation). The successful-path estimate is 28 provider operations, with failures and retries excluded. Live collection and human review remain pending; this preparation grants no additional request budget.

Use a local isolated dataset/corpus and no sensitive text. Record configured generation/embedding model IDs, vector dimension/finite-value validation, returned document/chunk IDs, distances, supplied context IDs/truncation, Recall@K/Hit Rate@K and sanitized errors. Independently inspect whether citations support the answer. A two-document sample can establish plumbing only; general retrieval quality and citation faithfulness require separate ground truth and a larger authorized study. A successful generation smoke does not imply embedding-model access.

## Deployment safeguards — no public release

Current Compose controls include loopback-only API binding, no published database port, restricted runtime DML credentials, a separate migration administrator, non-root/read-only application containers, dropped capabilities, body/connection limits and finite job retry/deadline policies. Both hosted workflows passed at `da60690`; these are controlled validation results.

The remaining public-release gaps are authentication/authorization and tenant isolation; TLS and ingress/body/read limits; installation-wide provider concurrency, rate and spend controls across API/worker replicas; protected secret provisioning/rotation; migration/rollback operations; encrypted offsite backups with retention and repeatable restore exercises; observability, alerting, retention and workload/outage validation. Existing accepted-result token metadata is not a complete spend ledger. Idempotent submission and fenced persistence cannot stop charges from an external response lost before acknowledgment.

The completed generated-data local dump/restore drill proves its documented snapshot checks only, not host-loss recovery, HA, PITR or production RPO/RTO. Keep the local demonstration private. A public release requires a separate concrete implementation/review and authorization; no URL publication, DNS/ingress change or deployment was performed here.

Current judge-collection preparation: [provider configuration](PROVIDER_CONFIGURATION.md) documents a deterministic offline selection, a ten-request live cap, checkpoints and key switching through environment configuration. The later bounded development and holdout runs are recorded separately; completing them does not authorize an expanded live-test budget. No premium key-entry UI or shared-server key ownership is implemented.

The simulated judge rehearsal paired all ten planned IDs with the frozen label snapshot and verified its SHA-256 hash. The subsequent live sample measured 60% agreement on the ten planned IDs.

## Offline acceptance

The packaged dashboard browser test submits a queued run, waits for the worker to complete it, and checks the resulting job, quality result, comparison, and judge-study status. Container CI runs this test against the simulated stack alongside the queue, RAG, and portfolio smoke commands. The judge-study view displays fifty recorded labels and twenty candidate-v2 pairs, with the development and response-level holdout scope disclosed.

The local acceptance run passed 148 Python tests and one packaged-dashboard browser test. Queue replay, two-document retrieval, the portfolio comparison, and the deterministic regression gate passed. The process smoke completed 64 jobs across four worker counts and recovered all four deliberate worker crashes. Local evidence is under `artifacts/offline-acceptance/`.

The full simulated judge rehearsal paired all 50 frozen labels. Its substring judge marked all 50 cases as failing, yielding 40 true negatives and 10 false negatives. The 80% agreement reflects the distribution of labels in this sample. The local report is `artifacts/offline-acceptance/judge-agreement.json`.

The historical PostgreSQL timeout remains an environment investigation. The recorded local captures include worker scheduling, transaction, blocker, and WAL timings. The next measurement needs a recurrence on the original or comparable hardware. See the [lock contention review](LOCK_CONTENTION_REVIEW.md).

## Next judge experiment

The live ten-example baseline measured 60% agreement. Its four false positives all involved instruction-injection responses. An experimental candidate-v2 prompt is available through the judge collector and has offline request-contract checks. The completed ten-request candidate run matched all ten planned human decisions and corrected all four baseline false positives. The completed response-level holdout also matched 10/10 labels. New Gemini processes now select candidate-v2 with prompt provenance stored in run snapshots and results. Thirty labeled responses remain available for future validation. Repeatability and generalization across new questions are still open.
