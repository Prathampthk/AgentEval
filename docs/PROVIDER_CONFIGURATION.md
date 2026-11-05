# Gemini configuration and usage controls

AgentEval already supports a user-supplied Gemini API key through the process environment. Fake mode remains the default and makes no external provider requests. There is no separate premium API integration or browser key storage in this milestone.

For a Gemini process, securely supply `GEMINI_API_KEY`, set `AGENTEVAL_PROVIDER=gemini`, and explicitly set `AGENTEVAL_MODEL`. The two recorded smoke evaluations used `gemini-3.1-flash-lite`; that sample does not establish future availability or billing eligibility. Keep keys out of chat, source control, command-line arguments, images and reports. Use a secret manager or a private terminal environment rather than pasting an actual key into a command saved in shell history.

To use another person's own key on their local installation, change `GEMINI_API_KEY` in that installation's environment and restart its API/worker processes with matching provider/model settings. Existing processes retain their earlier environment; editing a shell variable does not rotate a running client. Stored runs retain provider/model metadata, not the API key. Queued jobs have no key ownership or tenant isolation, so sharing one server among people with different keys is not currently supported. The supplied Compose demonstration intentionally uses fake mode; setting a host shell variable does not automatically change its containers to Gemini.

Free-tier versus billable use is controlled by the provider project/account, not a local `free` or `premium` toggle. AgentEval cannot determine a key's billing status. Before live requests, the operator must verify the project and permitted model in the provider console and explicitly agree the incremental request/spending limit. The present user instruction is **offline preparation only** while that status is uncertain. No live request is authorized by this document or by possession of a key. Consult the provider's [billing documentation](https://ai.google.dev/gemini-api/docs/billing) and [key management documentation](https://ai.google.dev/gemini-api/docs/api-key) in the provider console workflow.

## Prepared judge sample

The user has supplied fifty valid human labels, frozen locally before any new predictions. Raw labels and reviewer identifiers remain ignored. The committed completion record contains their file hash and aggregate counts only.

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
