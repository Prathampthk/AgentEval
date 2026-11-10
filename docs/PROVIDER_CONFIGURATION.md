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

Keep simulated-provider comparisons explicitly simulated. No simulated prediction is evidence for Gemini accuracy. Existing `reports/judge_validation.json` correctly remains BLOCKED with fifty human labels and zero paired predictions.

The optional hosted live workflow remains manual, disabled by default and capped at ten calls. Repository secrets/variables configure it separately; it has no access to ignored local human labels. It preserves partial prediction/metadata artifacts on failure, but dispatch still requires explicit usage authorization. A future hosted bring-your-own-key feature requires authentication, tenant-specific secret storage, job ownership, distributed quotas and spending controls before implementation or public deployment.
