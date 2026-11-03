# Milestone 7 — RAG evidence

The full suite passed 101 tests before one additional HTTP-route test; the final suite result is recorded below. Real PostgreSQL tests verify ingestion, duplicate reuse, cosine retrieval of the expected source, Recall@1/Hit Rate@1 of 1 for a controlled simulated example, exclusion of incompatible embedding models, and rollback-free rejection of invalid embeddings before document insertion. Unit tests verify chunk overlap/tail retention and vector validation. SDK contract tests verify requested dimensions and invalid embedding responses.

These checks use simulated hashed-word embeddings, not live semantic Gemini embeddings. No live-provider retrieval accuracy, latency or cost claim is made. The controlled corpus is not a benchmark. See RAG.md for security and scope limitations.

Final full-suite validation: **102 passed**, zero failures/errors/skips, one pre-existing Starlette deprecation warning. Lint and formatting passed. The pgvector image change retained the existing data directory and stopped prior container.
