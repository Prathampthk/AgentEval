# Small RAG evaluation target

The pipeline accepts plain text only (no URLs, filesystem paths or arbitrary document parsers), splits it into 100-word chunks with 20-word overlap, embeds chunks, stores 768-dimensional vectors in PostgreSQL/pgvector, retrieves exact cosine-nearest chunks, and constructs context with document/chunk identifiers before generation.

Routes: POST /documents (`title`, `content` up to 6,000 characters); POST /rag/ask (`question`, `k` 1–10); POST /rag/evaluate (also `expected_answer` and `expected_document_ids`). Ingestion allows at most 20 chunks, runs embedding calls sequentially outside a transaction, then inserts document/chunks atomically. Exact duplicate content reuses stored embeddings for the same provider/model; concurrent duplicate ingestion may repeat external calls before the uniqueness constraint resolves insertion.

Fake mode uses normalized hashed word counts, explicitly labeled simulated. It demonstrates storage/retrieval mechanics, not semantic embedding quality. Gemini uses the official SDK and AGENTEVAL_EMBEDDING_MODEL (default gemini-embedding-001), requesting 768 dimensions. Provider and model are stored with every chunk and filtered during retrieval; incompatible embeddings are never mixed. The recorded two-document live smoke used gemini-embedding-001 and gemini-3.1-flash-lite.

Retrieval returns chunk IDs, source document IDs and cosine distances. Recall@K measures the fraction of expected document IDs found among the top K chunks; Hit Rate@K indicates any match. Multiple chunks may come from the same document. These metrics depend on accurate ground truth and do not measure complete answer correctness. RAG evaluation also applies rubric v1 to the generated response. Expected answers are never passed into generation.

Exact search is intentional for this small controlled corpus; there is no approximate index or scale/performance claim. Retrieved text is untrusted. Prompts request citations, but citation faithfulness is not independently verified. Groundedness scores remain judge opinions. All RAG routes are request-scoped and share the API execution limit; document ingestion and RAG requests are not durable background jobs yet.

Migration 0004 installs the vector extension and creates documents/document_chunks. The local and CI image is digest-pinned pgvector/PostgreSQL 17. On the existing cloud instance the prior container was stopped and retained, and its data bind mount reused by the new container. Never start both containers against the same data directory. Fresh environments use the new image directly. Extension creation needs a migration administrator; the runtime role does not own schema changes.

## Context and timeout correction

Previously, valid retrieved chunks could assemble more than the evaluation contract's 12,000-character limit: asking worked while evaluating the same retrieval failed validation. Both paths now use a shared character budget. Context retains complete citation headers and, when needed, a prefix of the final included chunk. Responses add `context_chunk_ids`, `context_characters` and `context_truncated` so callers can identify the evidence actually supplied. Existing `retrieved` still describes the full ranked top-K retrieval; Recall@K/Hit Rate@K measure that retrieval, not whether all facts fit in generation context.

Truncation can omit decisive facts and affect correctness/groundedness; it is disclosed rather than silently presented as complete evidence. This is a character bound, not a tokenizer or universal model context limit. Rejecting all oversized retrievals would break useful existing asks; increasing the contract limit would increase resource/cost exposure. A shared budget preserves bounded behavior and aligns ask/evaluate contracts.

Unscored generation now uses the same provider timeout wrapper as embeddings. A provider timeout returns HTTP 504 with category `timeout` and `retryable=true`, matching the scored path; it no longer falls through to the generic database-unavailable handler. Database timeouts still retain database error handling.

Verification covers oversized real-pgvector retrieval through both HTTP paths, identical supplied evidence, intact citation headers, unchanged small contexts and controlled generation timeouts. No paid provider calls or new AI feature was introduced.

## Two-document smoke test

Start the simulated Compose API and run:

```bash
python3 scripts/rag_smoke.py
```

The command checks readiness, ingests two one-chunk synthetic documents, and submits one scored query. It checks both document IDs and their context chunks, finite cosine distances, Recall@2, and Hit Rate@2. The JSON report records model IDs, the answer, judge scores, and which expected document IDs appear in the answer. Inspect the answer alongside its sources when evaluating citation support.

For a Gemini smoke test, use the [local Gemini launcher](PROVIDER_CONFIGURATION.md) with a fresh corpus and a model and key approved for the intended usage. Run the following after confirming the allowance for five provider operations:

```bash
python3 scripts/rag_smoke.py --live
```

The live command targets the Gemini stack on port 8012 and checks provider identity before ingestion. The successful path uses two document embeddings, one query embedding, one generation request and one judge request. The script stops at the first failure and retains the stage and available results under ignored `artifacts/`. Each invocation adds two synthetic documents and may consume a fresh set of requests. Use `--port` for a different loopback port.

The simulated rehearsal completed with Recall@2 and Hit Rate@2 of 1.0 against a fresh Compose database. Hosted container checks now exercise the same simulated command.

## Recorded live smoke

The user-run report in reports/live-rag-smoke.json passed ingestion, retrieval and scored answer checks. Each source produced one chunk. Both expected documents were retrieved and supplied in 375 context characters with truncation false. Recall@2 and Hit Rate@2 were 1.0. The answer identified silver lanterns and cited both supporting document IDs. Inspection of the two synthetic source texts confirmed that claim.

Generation took 27.55 seconds and judgment 1.99 seconds in this single run. Returned generation/judge usage totaled 790 input and 161 output tokens. Embedding usage is absent from this report. The sample covers two synthetic documents and one query, with citation support inspected for that answer.

## Broader offline study preparation

Run `.venv/bin/python scripts/prepare_rag_study.py` to prepare a frozen fixture, request plan and empty human-review sheet under ignored `artifacts/rag-study-v1/`. Use `--output-dir` with a fresh directory for another preparation; existing directories are refused before any writes. The script makes no network requests and requires no API key. Fixture bytes are preserved with their SHA-256, and the local files use restrictive permissions.

The authored fixture in `examples/rag_study.json` has six synthetic documents and eight questions: six answerable and two unanswerable. It includes paraphrases, similar expedition names, superseded facts, multiple supporting records and an untrusted grading instruction. Expected answers and document IDs are authored test ground truth, not human labels or measured model results. This small controlled set is preparation for a study, not a representative retrieval benchmark.

A fresh successful execution would require six document embeddings, eight query embeddings, eight generations and six judgments: 28 operations. The plan does not authorize these calls, account for token costs or include failures/retries. Review provider-side usage, agree a separate request ceiling and pacing, and implement checkpointed collection before running live. A fresh isolated corpus is required to avoid contamination from prior documents. The fixture IDs must be mapped to returned database IDs. No live collector is provided by this preparation command.

Answerable questions should use `/rag/evaluate`. Unanswerable questions should use `/rag/ask`, because the scored endpoint requires at least one expected document. Their Recall@K and Hit Rate@K must remain null; an empty expected set is not a retrieval success. Report answerable retrieval metrics separately from manually reviewed abstention behavior.

After collection, populate the review sheet with actual answers and the exact evidence supplied to generation, preserving the fixture hash and question IDs. A human must then review answer support, citation support and appropriate abstention against that evidence. Missing citations or unsupported claims fail citation support; mark abstention assessment inapplicable when appropriate and explain ambiguity in notes. Keep judge scores and fixture categories out of the human handoff. Never fill the human decision fields from expected answers or judge outputs. All review fields remain null at preparation time.
