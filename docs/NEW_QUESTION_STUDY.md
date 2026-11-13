# New-question and repeatability pilot

This is an agent-authored synthetic pilot, not representative application data or human ground truth. Ten responses cover five fictional reference questions, with two variants per question. None exactly matches a normalized question in the original judge fixture. That check does not prove semantic independence; human review is still needed. The existing candidate-v2 prompt must remain unchanged during collection and analysis.

## Offline preparation

```bash
.venv/bin/python scripts/prepare_new_question_study.py
```

The helper creates a new ignored `artifacts/judge-new-questions/` directory, freezes fixture bytes/hash and saves a shuffled category-free packet and empty labels. Existing output directories are refused, preserving prior human work. No provider modules, credentials or network calls are used. The committed fixture contains synthetic questions, reference facts and responses; it contains no human decisions.

## Genuine human handoff

Read `artifacts/judge-new-questions/human_review_packet.json`. For each example, compare its response with its question, expected answer and context. In `artifacts/judge-new-questions/human_labels.json`, set only `human_pass`, `labeler` and optional `notes`. Follow the strict v1 rubric in [HUMAN_LABELING.md](HUMAN_LABELING.md): a passing response must be fully correct, relevant and supported; partial correctness, unsupported additions and abstention fail. Use a personal reviewer identifier; keep ambiguous cases in notes. Leave undecided responses null. Do not inspect categories or future model predictions before reviewing. The agent must not fill these decisions.

Before collection, validate all ten genuine labels and attribution, preserve the original and freeze a read-only private snapshot/hash. Confirm references and disclose that a single reviewer and synthetic facts limit the study. These steps are still pending; preparation alone is not completed review.

## Proposed collection protocol — not authorized

Use the frozen ten-response packet in three sequential repetitions with candidate-v2 and one fixed model/configuration. Proposed successful-path size is 30 judge operations. Agree a fresh attempted-request ceiling and check provider project quota/billing first; earlier allowances are consumed. Retain failed/uncertain attempts, stop at the first failure, disable automatic retry and preserve every repetition under a new output path. Pacing should be confirmed against current provider limits at authorization time.

The existing `judge_examples.py` CLI still targets the original study. Do not use its defaults for this pilot. A dedicated frozen-source collector and repeatability analysis must be implemented and verified offline before live execution. This packet does not activate any live collection.

Predeclare analysis before seeing predictions: report each repetition's confusion matrix/agreement against genuine labels, per-response changes across repetitions, and distinct question count separately from response count. Keep repeated predictions separate rather than pooling them as independent observations. Report results as a five-question synthetic pilot; do not tune the prompt on these results and still call them untouched validation. New prompt development would require a later independently held-out question set.

## Other acceptance boundaries

The hardware-dependent lock recurrence, approved private-server installation and offsite recovery remain separate. See [project completion](PROJECT_COMPLETION.md). This study preparation authorizes none of those operations.
