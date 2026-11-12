# Gemini configuration and usage controls

AgentEval already supports a user-supplied Gemini API key through the process environment. Fake mode remains the default and makes no external provider requests. There is no separate premium API integration or browser key storage in this milestone.

For a Gemini process, securely supply `GEMINI_API_KEY`, set `AGENTEVAL_PROVIDER=gemini`, and explicitly set `AGENTEVAL_MODEL`. The two recorded smoke evaluations used `gemini-3.1-flash-lite`; that sample does not establish future availability or billing eligibility. Keep keys out of chat, source control, command-line arguments, images and reports. Use a secret manager or a private terminal environment rather than pasting an actual key into a command saved in shell history.

On macOS or Linux, from a checkout with Python 3.12+ and Docker Compose, run `python3 scripts/run_gemini.py --model gemini-3.1-flash-lite` with a model available to your project. The launcher reads `GEMINI_API_KEY` from the environment or prompts with terminal echo disabled. It builds the application, initializes PostgreSQL, and applies the Gemini configuration to the API and worker. The dashboard is at `http://127.0.0.1:8012/dashboard/`. Use `--port` if that port is occupied. Readiness verifies application and database startup. Your first submitted evaluation checks provider access and uses one generation and one judge request per attempt.

The launcher passes the key to the API and worker as runtime environment configuration. Treat Docker access as privileged because it can inspect container environment variables. The Gemini stack uses its own Compose project and PostgreSQL volume. Rerun the launcher with a replacement key to recreate the affected services. Finish queued work before switching models because workers claim jobs for their configured provider and model.

Stop the local Gemini stack from the repository root with:

```bash
docker compose -p agenteval-gemini --env-file .local/compose.env down
```

The command preserves the database volume. Queued jobs have no key ownership or tenant isolation. Use a separate local installation for each person's credentials.

Free-tier versus billable use is controlled by the provider project/account, not a local `free` or `premium` toggle. AgentEval cannot determine a key's billing status. Before live requests, the operator must verify the project and permitted model in the provider console and explicitly agree the incremental request/spending limit. Consult the provider's [billing documentation](https://ai.google.dev/gemini-api/docs/billing) and [key management documentation](https://ai.google.dev/gemini-api/docs/api-key) in the provider console workflow.

## Prepared judge sample

The user has supplied fifty valid human labels, frozen locally before any new predictions. This study is prepared offline while billing eligibility for the study project is unconfirmed. Raw labels and reviewer identifiers remain ignored. The committed completion record contains their file hash and aggregate counts only.

Prepare a deterministic shuffled selection without constructing a provider client:

```bash
.venv/bin/python scripts/judge_examples.py --plan --limit 10 --seed 42 --output artifacts/judge-plan-new.json
```

This plan spans the source set instead of taking its first ten rows. It is not representative or statistically powered. The ten selected IDs are reproducible for the same source file and seed. Neither selection nor collection reads human decisions.

After billing eligibility and the request allowance are separately confirmed, the prepared collector can collect at most ten live judge responses per invocation using explicit `--live`. It runs sequentially, defaults to a six-second delay between requests, has a thirty-second request deadline and disables SDK/application retries. The delay is pacing, not an assurance of quota compliance. It stops on the first failure, including quota errors, and never automatically resumes. A new invocation is new usage, so do not rerun blindly.

Output JSON holds predictions, rubric/model provenance and returned token usage. A sibling `.meta.json` records the selected IDs, source hash, requests started, responses saved and completion/failure state. Each success is checkpointed; existing prediction/metadata paths are refused before collection. Partial predictions can be analyzed for their actual paired count, but must not be presented as completion of the planned sample. Successful-response usage excludes failed/uncertain requests and is not a complete billing ledger; `billing_tier_verified` remains false because the collector cannot verify it.

Analyze only after predictions exist, using the frozen human copy and a distinct output report:

```bash
.venv/bin/python -m agenteval.judge_validation --labels artifacts/human_labels.frozen-764d7e4b36f5.json --judgments artifacts/judge_predictions.json --output artifacts/judge-agreement.json
```

Keep simulated-provider comparisons explicitly simulated. No simulated prediction is evidence for Gemini accuracy. The recorded `reports/judge_validation.json` now contains fifty candidate-v2 pairs against fifty frozen human labels, with separate development and response-level validation reports.

The optional hosted live workflow remains manual, disabled by default and capped at ten calls. Repository secrets/variables configure it separately; it has no access to ignored local human labels. It preserves partial prediction/metadata artifacts on failure, but dispatch still requires explicit usage authorization. A future hosted bring-your-own-key feature requires authentication, tenant-specific secret storage, job ownership, distributed quotas and spending controls before implementation or public deployment.

The first live collection stopped after saving four responses. To continue a known prefix of a sample, `--offset 4 --limit 6 --seed 42` selects the remaining six IDs within the ten-example live cap. Use a fresh output path and verify combined IDs against the original plan before analysis. The saved four-plus-six sample was verified this way.

## Candidate judge prompt

The measured ten-example baseline used the v1 prompt and produced four false positives on instruction-injection responses. The collector now supports an experimental `--judge-prompt candidate-v2` option. It names the submitted text `candidate_response` and directs the judge to score the content present in that field. It explicitly addresses responses that consist entirely of grading instructions. The score scale remains rubric v1.

New Gemini API and worker processes select candidate-v2 by default. Set AGENTEVAL_JUDGE_PROMPT=v1, or pass --judge-prompt v1 to scripts/run_gemini.py, to select the baseline. Candidate predictions record their prompt version and SHA-256 fingerprint. Analysis rejects files containing multiple prompt versions or fingerprints. Historical files without those fields are interpreted as v1.

Prepare the same ten IDs offline with:

```bash
.venv/bin/python scripts/judge_examples.py --plan --limit 10 --seed 42 --judge-prompt candidate-v2 --output artifacts/judge-plan-candidate-new.json
```

After authorizing ten additional Gemini requests, collect with `--live --limit 10 --seed 42 --judge-prompt candidate-v2` and a fresh output path. Compare candidate and baseline reports against the frozen human labels. Offline tests verify the request payload and provenance. The completed ten-request candidate run matched all ten human decisions in the planned regression sample. Repeating the ten observed examples is a regression check. Those remaining forty responses were subsequently collected under separately authorized holdout and completion allowances.


The recorded comparison is in reports/judge-prompt-comparison.json. Baseline v1 agreed on six of ten examples (TP=2, TN=4, FP=4, FN=0). Candidate-v2 agreed on ten of ten (TP=2, TN=8, FP=0, FN=0). Its saved response usage totals 3,399 input tokens and 539 output tokens. The candidate was developed after examining failures on these same examples. Subsequent response-level validation matched 40/40 decisions, with underlying question overlap. New-question generalization and repeated-run stability remain pending.


## Persisted prompt provenance

After response-level holdout validation, candidate-v2 is the default for new Gemini processes. Restart the local API and worker together to load the release. Every new run snapshots the judge prompt version and fingerprint, and every result carries those fields. Queued jobs execute the prompt recorded at submission, even if the worker's default changes. Older runs without prompt metadata retain v1 semantics. Legacy idempotent submissions replay under v1, while an attempt to reuse the same key for a different prompt is a conflict.

Regression comparisons return INCONCLUSIVE when judge prompt versions or fingerprints differ. Old comparison artifacts default to v1 with an unknown fingerprint. The score scale remains rubric v1. The study collector keeps an explicit --judge-prompt selector for baseline and candidate experiments. Its live request cap remains ten per invocation, and --offset can select a later range of the fifty-example source.
