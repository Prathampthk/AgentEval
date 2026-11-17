# AgentEval app guide — plain language

This guide describes the current four-tab dashboard, not a proposed future interface. It is a local developer testing tool. You do not need to memorize every backend detail to use it, but you should know what the displayed evidence means.

## What someone would actually use it for

A developer changes a support bot's instructions, then reruns a saved set of questions and checks whether previously acceptable answers got worse. A student can use it to learn about evaluation, databases, background work and regression checks. A team could adapt it to its own representative test cases, with permission to use the data.

It is not a daily student productivity assistant, a trained model, a replacement for human fact-checking or a universal website/chatbot tester. The current app tests its built-in configured providers. Testing an arbitrary third-party chatbot needs an adapter; there is no “paste any chatbot URL” feature.

## Getting it running

Follow the full [README](../../README.md). Short version, from the cloned repository with Python 3.12+ and local Docker running:

```bash
python3 scripts/run_demo.py
```

Wait for `DEMO READY` and open http://127.0.0.1:8013/dashboard/. This launches a simulated provider and needs no API key. The first build needs internet. A source checkout alone does not start the API/database/worker. The launcher handles those services and builds the dashboard; no host Node/PostgreSQL/Python-package install is required for this path.

Use macOS/Linux or the documented WSL2 Linux environment with local Unix-socket Docker. Native PowerShell and remote/TCP Docker are not supported by this launcher. Docker needs available memory/disk; no hardware minimum was established. On another computer, `127.0.0.1` refers to that other computer, so my local URL is not a shared hosted website.

There is no login for the default loopback fake demo. Owner authentication belongs to an optional private deployment profile. Do not make this demo internet-accessible.

## Key terms before touching the controls

| Term | Meaning | Small example |
|---|---|---|
| Dataset | A saved collection of test cases | Questions about a support policy |
| Version | A label for an immutable dataset's contents | `1`, followed by `2` when cases change |
| Test case | One question, reference and optional source text | Capital of France / Paris / supporting context Paris |
| Expected answer | The reference used to judge, not sent to generation | Paris |
| Context | Supporting text the generator is allowed to use | A short policy excerpt |
| Prompt | Instructions for generating the answer | “Use the supplied context” |
| Run | One evaluation of a selected dataset/configuration | A baseline run before a prompt change |
| Job | One queued test case in a run | One pending evaluation task |
| Worker | A separate process that executes jobs | Picks up the queued question |
| Result | Accepted generated answer, rubric scores and metadata | Paris; correctness 2 |
| Provider/model | The service and model doing the work | Fake simulation, or configured Gemini |
| Baseline/candidate | Old/reference run and proposed/new run | Before versus after a change |
| Regression | A behavior that got worse after a change | Previously supported answer becomes unsupported |
| Rubric | Rules for scoring answers | Correctness, relevance, groundedness |
| Evidence/provenance | Results plus information identifying their source | Model/prompt version, dataset and saved report |

## Navigation and controls shared across views

| Control or display | What it does / means |
|---|---|
| **Overview**, **Runs**, **Compare**, **Judge study** | Switches views in the same workspace. The active tab is highlighted. |
| Workspace breadcrumb and LOCAL / CONTROLLED | Identify the current view and intended environment. They are labels, not environment/provider switch buttons. |
| **Refresh** | Reloads stored dashboard data; it does not rerun a model or retry a failed job. Data also refreshes approximately every five seconds. |
| Gray/disabled button | An action is busy or required selections are missing. For Compare, select both runs. For Submit, select a dataset. |
| Success notice | Confirms an action, e.g. “Dataset saved” or “Submission saved.” Submission saved does not mean execution finished. |
| Error notice | Displays a request/validation/server error. Fix the cause, preserve evidence and retry deliberately; do not repeatedly submit blindly. |
| Simulated notice | Some displayed records use placeholder provider behavior. Their score/latency is not live Gemini evidence. |
| `—` | Missing/unavailable, not zero. |
| Short run/job ID | The beginning of a longer unique identifier, not a score or ordering number. |
| AgentEval logo, footer, local-workspace text | Informational; they do not select a model, enable a server or create work. |

## Tab 1 — Overview

This is an aggregate of the local database, not just your selected dataset and not a live model benchmark.

| Display/control | Meaning |
|---|---|
| Evaluation runs | Total saved runs, including earlier rehearsals and different statuses. |
| Accepted results | Number of saved result rows, not external request attempts. Failed/uncertain/discarded external responses are not a complete part of this count. |
| Quality passes | Saved results whose pass rule succeeded. It is not the number of completed runs. |
| Average latency | Mean saved generation-plus-judging duration per result, in milliseconds. It excludes queue waiting and is not full run turnaround or provider billing. Very small fake durations do not describe Gemini speed. |
| Quality summary | Count of accepted results passing or not passing the rubric. A completed run can contain either. |
| Correctness | Whether the answer is factually correct for the reference question. |
| Relevance | Whether the response addresses what was asked. |
| Groundedness | Whether supplied context supports the answer. Missing context can make it unavailable; averages skip missing values. |
| Score bars | Mean 0–2 rubric scores. `2.00` is the top rubric score, not 200%, confidence or calibrated probability. |
| Job monitoring | Counts of jobs by execution state across the database. Jobs and runs are different units. |
| Latest run | Most recently created run and its execution status. |
| **Open runs** | Goes to Runs; it does not submit anything. |

The broad score interpretation is 0 = fails the criterion, 1 = partial fulfillment and 2 = full fulfillment, subject to the documented prompt/rubric. Fake mode uses intentionally simple checks and often produces only 0 or 2. It is not a nuanced AI evaluator.

### Execution states

| State | Meaning |
|---|---|
| PENDING | A job is waiting or eligible to be picked up; it may be waiting for retry time. |
| RUNNING | Work is active at the run/job level; a running queued run can contain pending jobs. |
| COMPLETED | Execution finished successfully. It does not itself mean the answer quality passed. |
| FAILED | Execution could not successfully finish within its policy; inspect error and earlier results. |
| CANCELED | Work was canceled, including possible deadline handling; earlier saved results may remain. |

## Tab 2 — Runs

### Create a dataset

| Field/button | How to use it |
|---|---|
| **Name** | A descriptive dataset name, e.g. `Library demo take1`. For a new rehearsal use a unique name or a new version. |
| **Version** | A dataset-content label, e.g. `1`. Changing the generation prompt does not require changing the dataset; changing its reference cases does. |
| **Test cases (JSON)** | A JSON list of objects. Use double quotes, no trailing commas and the exact field names below. |
| **Save dataset** | Stores the version and selects it. It creates no model calls. Equivalent existing name/version contents are reused; conflicting contents at that name/version are rejected instead of overwriting history. |

A valid single-case example (already similar to the default):

```json
[
  {
    "external_id": "capital",
    "question": "What is the capital of France?",
    "expected_answer": "Paris",
    "context": "Paris",
    "exact_match": true
  }
]
```

| JSON field | Meaning |
|---|---|
| `external_id` | Your unique case label within this dataset. Keep it stable for matching. |
| `question` | The input to answer. |
| `expected_answer` | The answer key for judging. The generator does not receive this field. |
| `context` | Optional supporting text; omit or use an empty string when there is no context. |
| `exact_match` | Optional extra strict text check. When true, generated/reference text must match after surrounding whitespace is stripped; case and remaining wording matter. A semantically correct longer answer can fail this condition. |

Save supports 1–20 cases, subject also to the overall 32-KiB request body limit and individual field limits. Do not paste large documents into this form or use real private student/customer information without permission. Dataset versions are immutable through supported app operations; there is no edit/delete button here.

### Submit evaluation

| Field/button | What happens |
|---|---|
| **Dataset version** | Selects a saved dataset; the option shows name, version and case count. Also determines the history shown below. |
| **Prompt** | Generation instructions for a new run. It does not edit the dataset or the judge prompt. Fake mode is not a meaningful test of prompt effectiveness; it returns deterministic context-based placeholder behavior. |
| **Submit run** | Saves queued work, then a worker executes it. Repeating a genuinely new submission can create another run and, in real mode, incur calls. One case normally generates once and judges once: two operations per attempt, with retries/uncertainty potentially adding work. |
| Submission saved | The queue accepted it; wait for completion and inspect results. |

The browser keeps an idempotency key for retrying an uncertain equivalent submission; after a successful submission it creates a fresh key next time. This is not an instruction to repeatedly click Submit, and it does not promise exactly-once external execution.

### Evaluation history

| Column/action | Meaning |
|---|---|
| **Run** short-ID button | Loads that run's details/jobs. Scroll down if the details are below the history table. |
| Status | Run execution state, not its overall quality score. |
| Model | Configured model identifier; fake mode is explicitly simulated. |
| Source | Simulated or Live provider. It is an information label, not a toggle. |
| Results | How many accepted case results are currently saved for the run; partial queued results may appear while work continues. |

Selecting another dataset clears selected run details and resets Compare selections. History survives reload/restart. There is no dashboard delete/reset history button.

### Evaluation details

| Item/control | Meaning |
|---|---|
| **Cancel run** | Appears for running runs. Requests cancellation of supported queued work; an already emitted external request may still execute/incur cost. It is not a refund or an undo of saved results. |
| Job | Short ID of the case's execution task. |
| Status | State of that job. |
| Attempts `1/3` | One job attempt started out of a maximum three, not one of three expected answers and not exactly one external API call. A case can involve generation plus judgment within each attempt. |
| Last error | Sanitized execution error category or `—`. Not the same as a low rubric score. |
| Question/Expected/Answer | Shows the input, stored reference and actual generated response. |
| QUALITY PASS / QUALITY FAIL | Result of the answer-quality rule, separate from execution status. |
| Rubric values | Per-answer correctness, relevance, groundedness, generally on 0–2. Groundedness may be missing without context. |
| Explanation | Judge reasoning, or an explicitly simulated checking explanation. It can be wrong; inspect the answer/context yourself. |
| No accepted results yet | Work is not finished, failed before acceptance or was canceled. It is not a zero quality score. |

Normal quality pass: correctness 2 AND relevance 2 AND groundedness 2 when there is context AND exact match not false when requested. A missing groundedness score without context is not automatically a fail.

## Tab 3 — Compare

| Field/button/display | Meaning |
|---|---|
| **Dataset version** | Pick the same saved version for both runs. Changing this clears baseline/candidate choices. |
| **Baseline** | Choose the reference/older run. |
| **Candidate** | Choose the proposed/newer run. |
| **Compare runs** | Compares stored results; no model request is made. Does not create a new generation run. |
| Paired cases | Cases present in both results by matching identifier. Completeness and compatibility still determine whether comparison is meaningful. |
| PASS | Changes stayed within configured quality policy. Does not mean perfect answers or a release/security approval. |
| FAIL | One or more configured limits were exceeded; read metrics/reasons. |
| INCONCLUSIVE | Not enough valid matching evidence, incomplete/failed execution or incompatible configuration. It is not an automatic pass or fail. |
| Reasons | Explanation of policy failure or why the comparison is not valid. |

Metric names replace underscores with spaces. `baseline pass rate`/`candidate pass rate` are fractions: `1.00` means all cases passed and `0.50` means half. Correctness is a mean on 0–2. Latency is mean saved generation-plus-judge milliseconds. Token metrics appear only when applicable to the policy and available; missing usage is not zero cost.

Current default policies allow at most a 0.05 absolute pass-rate drop (five percentage points) and 0.25 average correctness drop; at least one case is required. Latency/token ratio gates are optional and not on by default. These are engineering demonstration thresholds, not statistical tests. The dashboard does not offer controls to tune them.

Compatibility checks include dataset/version identity, case coverage, provider/model, rubric, judge prompt version/fingerprint and simulation mode. To compare a generation prompt change fairly, keep the dataset and judge configuration the same. Do not compare different datasets or an old/new judge prompt and call it a clean generation regression result. Comparing a completed run with itself is valid as a workflow sanity check, not evidence of an improvement.

## Tab 4 — Judge study

This reads the packaged `reports/judge_validation.json`. It does not label your new run, start Gemini or automatically absorb new research reports.

| Display | Meaning |
|---|---|
| Human labels | Number of genuine human-reviewed response decisions recorded in the packaged report. |
| Paired examples | Human decisions matched to model judge decisions by ID. |
| Agreement | Fraction of paired decisions matching. Displayed as a percentage here, unlike pass-rate fractions in Compare. |
| Judge prompt | Which judge instruction version produced the predictions. Changing the generation Prompt box does not change this. |
| Scope text | Development/validation split and overlapping-question limitations. |
| TP | Human passes; judge also passes. |
| TN | Human fails; judge also fails. |
| FP | Human fails; judge incorrectly passes. An unsafe “looks fine” decision. |
| FN | Human passes; judge incorrectly fails. An overly strict decision. |
| Disagreements | IDs/categories where the paired human/model binary decisions differ. No disagreements on this sample does not imply a perfect judge. |

Current packaged study: 50 human labels, 50 pairs, 100% observed agreement; TP=10, TN=40, FP=0, FN=0. Say “agreement on this sample,” never “100% accurate.” It contains ten development and forty response-level validation responses across ten overlapping underlying questions, one reviewer and synthetic examples. The archived first prompt had four false positives and matched 6/10.

The separate five-new-question repeatability pilot and eight-question RAG human review are committed reports, not additional cards in this tab. Do not sum 50 plus 30 repeated predictions and claim 80 independent human examples.

## Features outside the dashboard

- **RAG:** document ingestion, embedding search, retrieved sources and answer evaluation exist as API/script workflows. There is no file-upload/RAG tab. Exact cosine search has no large-corpus scale claim. Finding an expected document does not alone prove the answer/citation is supported.
- **API documentation:** the running backend exposes `/docs`; use it only after understanding which requests create work. The dashboard doesn't display every backend operation.
- **Crash/restore/benchmark tests:** separate tools and dedicated databases; do not terminate a demo database on stage. The normal launcher is not a full test-suite run.
- **Human labeling:** genuine offline JSON reviews, not generated labels and not an in-dashboard task.
- **Model/key switching:** local launch configuration, not a browser dropdown or secret-storage page.
- **Server backups/authentication:** optional private-server preparation. It is not a public hosted service or multi-user system.

## Optional Gemini mode — only when you intentionally want real calls

```bash
python3 scripts/run_gemini.py --model gemini-3.1-flash-lite
```

Use a model actually available in your Gemini project. Enter your own Gemini key at the hidden terminal prompt; never paste it into chat, the dataset, screenshots or Git. The launcher creates a separate local Gemini project, normally on port 8012. It is not the same as the fake demo at 8013. A student who only wants to run/test the app does not need this step.

The key's billing/quota/free-tier status belongs to its provider project; a working key does not prove requests are free. Ordinary evaluations can make two model operations per case per attempt, and retries/uncertainty can add calls. Use a very small intentional sample and check provider usage. The existing project research allowances are consumed; no further research calls are authorized by this guide. A premium key is not a special app mode: it is a compatible Gemini project/key/model configuration. OpenAI or arbitrary other API keys are not supported by the current provider adapter.

No real Gemini calls are part of the class demo. The recorded live results can be presented without rerunning them.

## Common mistakes and what to do

| Situation | Practical response |
|---|---|
| “Can I paste a new dataset over v1?” | Save a new version/name; don't overwrite evidence. Equivalent data may reuse an existing version. |
| Save reports invalid JSON | Restore the valid default example. Check double quotes, brackets and no trailing comma. |
| Save reports conflict | That name/version already has different contents. Use a new name/version. |
| Submit button disabled | Save/select a dataset and wait for any current request to finish. |
| Pending job | Check that the worker is running, use Refresh and preserve the run. Do not keep submitting duplicates. |
| Completed but QUALITY FAIL | Execution succeeded; answer rubric/exact match failed. Inspect the answer/explanation. |
| Compare inconclusive | Read the reason; choose completed compatible runs of the same dataset. |
| Scores look perfect in fake mode | Expected for simple fixtures; not a real model-quality result. |
| Changed prompt but fake answer did not change | Fake mode is a deterministic workflow placeholder, not semantic prompt evaluation. |
| Judge study values don't change after a new run | It reads a saved study report, not live analysis of your current dataset. |
| Counts differ from screenshots | Rehearsals add history; counts are not hard-coded demo targets. |
| Cancel didn't erase results or prevent all charges | Cancellation is cooperative and preserves earlier evidence; emitted requests can still execute. |
| Closing the browser didn't stop work | Backend/worker processes continue. Use the documented Compose stop command to stop services. |
| App fails after reboot | Start Docker, then rerun the launcher from the same checkout. Keep the same project and protected credentials. |
| Second clone is refused | Use a separate `agenteval-demo-NAME` project and port, following README. Do not delete the first copy's volume. |
| Platform unavailable on a student's computer | Report the actual OS/Docker/Python restriction. Use recorded evidence as a clearly labeled fallback, not proof of that student's local execution. |

## One-minute self-check before you defend the project

Explain these aloud without notes: one run versus one job; completed versus quality pass; fake versus real; generation prompt versus judge prompt; agreement versus accuracy; why comparison can be inconclusive; why external calls may repeat after a crash. If any answer is unclear, reread that section and rehearse the demo again.
