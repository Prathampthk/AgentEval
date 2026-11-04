# Human/AI judge study — data collection pending

The 50 prepared examples in examples/judge_study.json contain ten simple controlled questions with five response variants each. Categories include direct answers, abstentions, factual errors, question echoing and attempted rubric injection. They are a convenience sample, not a representative benchmark.

Before looking at AI predictions, a human should copy examples/human_labels.template.json to an ignored local file, review each example and set human_pass to true or false with a labeler identifier and notes. Positive means the response is fully correct, directly relevant, and fully supported by the context. Partial correctness, unsupported claims and abstention fail this strict binary rubric v1. Record ambiguous cases in notes; disagreement analysis should discuss them. Leave unreviewed labels null. Do not ask an LLM to fill human labels.

Optional prediction command (default fake, NOT a live AI study):

```
AGENTEVAL_PROVIDER=fake .venv/bin/python scripts/judge_examples.py --limit 50
.venv/bin/python -m agenteval.judge_validation --labels artifacts/human_labels.json --judgments artifacts/judge_predictions.json
```

Gemini mode additionally requires securely configured credentials/model, an agreed budget and explicit --live. Do not run 50 live calls without authorization.

The analysis defines quality_pass as positive and reports paired sample size, agreement, TP/TN/FP/FN, precision, recall, false-positive and false-negative rates, and disagreement identifiers/categories. Undefined ratios are null, not zero. Unknown/duplicate IDs and incompatible rubrics are rejected. Labels and AI predictions remain separate files.

reports/judge_validation.json currently reports BLOCKED, 50 available examples, zero human labels and no measured accuracy. This is the honest study status. The analysis implementation is tested using explicitly synthetic unit fixtures; those fixtures are not human-study evidence.

To prepare a category-blinded review packet and a separate writable label template:

```bash
.venv/bin/python scripts/prepare_human_review.py
```

Review `artifacts/human_review_packet.json` against this rubric and enter your decisions in `artifacts/human_labels.json`. The packet uses a deterministic shuffled order and omits category hints; IDs remain intact for matching. The script never fills a label or overwrites existing files. Both outputs are ignored local files. The original ten-question convenience-sample limitation remains; shuffling does not make it representative. Read neither AI predictions nor category hints before labeling, and keep ambiguous cases in notes.
