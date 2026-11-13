# Small RAG evaluation target

The pipeline accepts plain text only (no URLs, filesystem paths or arbitrary document parsers), splits it into 100-word chunks with 20-word overlap, embeds chunks, stores 768-dimensional vectors in PostgreSQL/pgvector, retrieves exact cosine-nearest chunks, and constructs context with document/chunk identifiers before generation.

Routes: POST /documents (`title`, `content` up to 6,000 characters); POST /rag/ask (`question`, `k` 1–10); POST /rag/evaluate (also `expected_answer` and `expected_document_ids`). Ingestion allows at most 20 chunks, runs embedding calls sequentially outside a transaction, then inserts document/chunks atomically. Exact duplicate content reuses stored embeddings for the same provider/model; concurrent duplicate ingestion may repeat external calls before the uniqueness constraint resolves insertion.

Fake mode uses normalized hashed word counts, explicitly labeled simulated. It demonstrates storage/retrieval mechanics, not semantic embedding quality. Gemini uses the official SDK and AGENTEVAL_EMBEDDING_MODEL (default gemini-embedding-001), requesting 768 dimensions. Provider and model are stored with every chunk and filtered during retrieval; incompatible embeddings are never mixed. The recorded two-document live smoke used gemini-embedding-001 and gemini-3.1-flash-lite.

Retrieval returns chunk IDs, source document IDs and cosine distances. Recall@K measures the fraction of expected document IDs found among the top K chunks; Hit Rate@K indicates any match. Multiple chunks may come from the same document. These metrics depend on accurate ground truth and do not measure complete answer correctness. RAG evaluation also applies rubric v1 to the generated response. Expected answers are never passed into generation.

Exact search is intentional for this small controlled corpus; there is no approximate index or scale/performance claim. Retrieved text is untrusted. Prompts request citations; the small human-reviewed study below provides scoped evidence, not general citation-faithfulness calibration. Groundedness scores remain judge opinions. All RAG routes are request-scoped and share the API execution limit; document ingestion and RAG requests are not durable background jobs yet.

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

A fresh successful execution would require six document embeddings, eight query embeddings, eight generations and six judgments: 28 operations. The plan does not authorize these calls, account for token costs or include failures/retries. Review provider-side usage, agree a separate request ceiling and pacing, and implement checkpointed collection before running live. A fresh isolated corpus is required to avoid contamination from prior documents. The fixture IDs must be mapped to returned database IDs. The preparation command does not collect answers; use the separately budgeted collector below.

Answerable questions should use `/rag/evaluate`. Unanswerable questions should use `/rag/ask`, because the scored endpoint requires at least one expected document. Their Recall@K and Hit Rate@K must remain null; an empty expected set is not a retrieval success. Report answerable retrieval metrics separately from manually reviewed abstention behavior.

After collection, populate the review sheet with actual answers and the exact evidence supplied to generation, preserving the fixture hash and question IDs. A human must then review answer support, citation support and appropriate abstention against that evidence. Missing citations or unsupported claims fail citation support; mark abstention assessment inapplicable when appropriate and explain ambiguity in notes. Keep judge scores and fixture categories out of the human handoff. Never fill the human decision fields from expected answers or judge outputs. All review fields remain null at preparation time.

### Checkpointed collection

`scripts/collect_rag_study.py` executes the fixture through the RAG library against an explicitly configured dedicated database. It refuses any corpus that already contains documents, requires a fresh output directory and supports only one-chunk documents for exact operation accounting. It does not clear a corpus or resume a stopped run. The existing API/worker database should never be used for this experiment.

The default provider is fake. In a fresh migrated isolated database, run `.venv/bin/python scripts/collect_rag_study.py --source artifacts/rag-study-v1-frozen/fixture.json --output-dir artifacts/rag-study-rehearsal --max-operations 28 --delay-seconds 0`. Configure its database URL privately. Gemini requires explicit `--live`, provider/model/key environment configuration and a separately authorized budget. This collector caps operations at 28 per invocation, not across invocations or applications. SDK retries are disabled by the shared provider context. Count-before-dispatch checkpoints conservatively retain uncertain attempts; the collector stops at its first error and does not retry.

Collection records actual ranked chunks, supplied context, generated answers, available generation/judge usage and model/prompt provenance. It uses the library retrieval and bounded-context code, then requests answers with citations and abstention when evidence is insufficient. This study-specific generation instruction differs from the original smoke instruction. Questions with evidence are judged separately against authored reference answers; the references are never passed into generation. Unknown-answer questions have null retrieval metrics and no judge call. The default 13-second pacing applies between operation starts, outside provider timeouts. It is not quota enforcement or proof of free-tier eligibility. Only the collected answers and supplied context belong in the human review handoff; judge opinions remain separate.

Create that separate handoff with `.venv/bin/python scripts/prepare_rag_answers.py --collection PATH/collection.json --output PATH/human_review_answers.json`. The output must be new. Actual answers and supplied context are copied; expected answers and judge scores are omitted. All support, citation, abstention and reviewer fields remain null. Partial collections identify missing answers as not ready for review. This helper preserves existing review files and never submits a provider request.

### Complete and validate human review

In the local review packet, change only `answer_supported`, `citations_supported`, `appropriate_abstention`, `reviewer` and `notes`. Use JSON `true` or `false` for decisions. `null` means unreviewed. Assess each answer using its supplied evidence; unsupported factual claims fail answer support. Citation support means any citations used actually support their associated claims; missing required citations fail this check. For an evidence-based abstention with no factual answer or citations, explain the inapplicable citation check in notes and use true only if there are no unsupported citations or citation obligations. Record ambiguities in notes.

The first six questions are answerable: leave `appropriate_abstention` null for those. The final two questions have no answer in the corpus: set `appropriate_abstention` to true only if the answer acknowledges insufficient evidence without inventing the missing fact. Enter your reviewer identifier for each completed entry. Never alter the copied answer, question or supplied evidence. Review without reading the AI judge scores.

Run `.venv/bin/python scripts/summarize_rag_review.py --reviews artifacts/rag-study-live-2026-11-12/human_review_answers.json --output artifacts/rag-human-review-summary.json`. It validates the fixture fingerprint, question IDs, copied evidence, strict boolean decisions and reviewer attribution. Existing output files are refused. It never modifies the review file. Incomplete entries remain pending and contribute no positive or negative decisions; rates are null when there are no completed reviews. Summary output omits reviewer identifiers and notes. Keep the filled raw review packet under ignored `artifacts/` and preserve a snapshot/hash before any later experiment. No provider access is involved.

### Recorded eight-question collection

The authorized live collection completed 28 attempted operations without a recorded failure or automatic retry. All expected documents appeared in the top three results for six answerable queries; both mean Recall@3 and Hit Rate@3 were 1.0 on this fixture. The two unanswerable questions retain null retrieval metrics. Eight actual answers and supplied contexts are preserved in `reports/live-rag-study-v1.json`; human support/citation/abstention decisions were unfilled at collection time and have since been completed as recorded below. Saved generation/judgment usage totals 6,741 input and 805 output tokens, excluding embeddings. See `reports/live-rag-study-v1-summary.json` for scope and provenance. The isolated database was temporary; repeating collection consumes a new request budget.

## Completed human review

The user completed all eight reviews and confirmed the saved file. The offline validator matched every question, actual answer and supplied evidence block to the frozen fixture/collection, checked strict decision types and nonempty attribution, and found no missing or duplicate IDs. A read-only ignored snapshot was created; the writable user file was preserved byte-for-byte. Reviewer identifiers and notes remain private. See [aggregate results](../reports/rag-human-review-completion.json) and [provenance](../reports/rag-human-review-provenance.json).

For the six answerable questions, the user marked 6/6 answers supported and 6/6 citation assessments supported. For the two unanswerable questions, the user marked 2/2 abstentions appropriate. These are user-supplied decisions, not generated labels or copied AI scores. Unanswerable citation assessments are kept separate from factual-answer citation support. The earlier collection-time summary and zero-review status record remain historical evidence. No new provider calls were needed.

This is one user review of eight answers from six authored synthetic documents. It does not establish representative accuracy, repeatability, inter-rater agreement or general citation faithfulness. Further studies need new questions/corpora, genuine human decisions and a separately approved live-request allowance.
