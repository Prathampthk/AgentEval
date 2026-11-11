# Separate validation boundaries

The two completed Gemini smoke evaluations validate a narrow generation/judgment path. They are not evidence for semantic retrieval, human agreement or deployment safety. No paid calls or public deployment are authorized by this plan.

## Human review

The user completed all 50 labels under ignored `artifacts/`; validation found 10 pass and 40 fail. Decisions are frozen locally with a committed provenance hash (`reports/human-labels-completion.json`). Instructions and strict rubric are in [HUMAN_LABELING.md](HUMAN_LABELING.md). Judge predictions and agreement remain pending. A human should review without AI predictions/category hints, supply their own identifier and keep ambiguity notes. The completed labels have been frozen before new predictions. Fifty variants of ten questions are a convenience sample, so later agreement must disclose that dependency and scope. Never replace unreviewed nulls with generated labels.

## Live RAG assessment — pending budget approval

Live embeddings have not run. First agree a hard incremental request/spend ceiling and check provider-side usage, including earlier failed or discarded calls. The accepted smoke results record 418 input and 126 output tokens; that cannot establish total spend or the unused portion of an earlier allowance. Do not dispatch the optional hosted live workflow merely because its boolean input exists.

The [two-document smoke command](RAG.md#two-document-smoke-test) now runs through the local Compose API and records its evidence. Its simulated rehearsal passed. The live path remains pending and uses five provider operations on success, including three embeddings, one generation request and one judgment call. Account for attempted requests when investigating any failure.

Use a local isolated dataset/corpus and no sensitive text. Record configured generation/embedding model IDs, vector dimension/finite-value validation, returned document/chunk IDs, distances, supplied context IDs/truncation, Recall@K/Hit Rate@K and sanitized errors. Independently inspect whether citations support the answer. A two-document sample can establish plumbing only; general retrieval quality and citation faithfulness require separate ground truth and a larger authorized study. A successful generation smoke does not imply embedding-model access.

## Deployment safeguards — no public release

Current Compose controls include loopback-only API binding, no published database port, restricted runtime DML credentials, a separate migration administrator, non-root/read-only application containers, dropped capabilities, body/connection limits and finite job retry/deadline policies. Both hosted workflows passed at `da60690`; these are controlled validation results.

The remaining public-release gaps are authentication/authorization and tenant isolation; TLS and ingress/body/read limits; installation-wide provider concurrency, rate and spend controls across API/worker replicas; protected secret provisioning/rotation; migration/rollback operations; encrypted offsite backups with retention and repeatable restore exercises; observability, alerting, retention and workload/outage validation. Existing accepted-result token metadata is not a complete spend ledger. Idempotent submission and fenced persistence cannot stop charges from an external response lost before acknowledgment.

The completed generated-data local dump/restore drill proves its documented snapshot checks only, not host-loss recovery, HA, PITR or production RPO/RTO. Keep the local demonstration private. A public release requires a separate concrete implementation/review and authorization; no URL publication, DNS/ingress change or deployment was performed here.

Current judge-collection preparation: [provider configuration](PROVIDER_CONFIGURATION.md) documents a deterministic offline selection, a ten-request live cap, checkpoints and key switching through environment configuration. The user requested no Gemini calls until the current project’s free-tier/billing status is confirmed. No premium key-entry UI or shared-server key ownership is implemented.

The simulated judge rehearsal paired all ten planned IDs with the frozen label snapshot and verified its SHA-256 hash. Live agreement remains pending.
