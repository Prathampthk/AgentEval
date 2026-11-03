# Evaluation methodology — milestone 1

Generation receives question, context and the selected instruction. The expected answer is sent only to the judge. User-supplied question/context may themselves contain answers; field isolation cannot prevent that.

Rubric v1 uses ordinal integer scores, not calibrated probabilities:

| Metric | 0 | 1 | 2 |
|---|---|---|---|
| Correctness | Incorrect | Partially correct | Fully correct against reference |
| Relevance | Off topic | Partly addresses question | Directly addresses question |
| Groundedness | Unsupported | Partly supported | All claims supported |

Groundedness must be null without context and present with context. Strict schemas reject unknown fields, invalid scores and empty explanations. A pass requires correctness and relevance of 2, groundedness of 2 when context exists, and exact match when requested. Exact match trims surrounding whitespace but preserves case and internal whitespace. These conservative demonstration thresholds have not been empirically calibrated.

The fake provider is a controlled fixture: context echo, case-insensitive reference substring detection and simple support checks. Do not interpret its outputs as real judge accuracy.

Gemini structured judgment includes model identity, rubric version, separate generation/judge latencies and separate nullable usage counts. Temperature zero does not ensure determinism. Prompts label judgment inputs as untrusted, but prompt injection remains a limitation. Using the same model for generation and judgment can cause correlated errors. Human agreement, repeated-judge stability, false positives and false negatives have not been measured.

The stateless endpoint uses caller-provided version labels. The new persisted /datasets and /runs workflow stores versions and rejects conflicting changes to existing versions. No cross-run comparison, retrieval metric, embedding, human labeling or regression policy exists at this milestone.
