# AgentEval: timed presenter script and demo

Use this as rehearsal notes, not text to put on slides. Bracketed directions are actions, not spoken words. The 12:00 schedule includes a 3:00 demo. It is a planning budget, not a guarantee of your reading speed: rehearse aloud with clicks and a timer. Aim for roughly 125–140 spoken words/minute, pause after diagrams, and finish early rather than filling silence. Questions are additional unless your professor includes them in the same limit. The supplied rubric is the basis here; additional Canvas requirements still need your own check.

## Run of show

| Slide | Topic | Duration | Clock at end |
|---|---|---:|---:|
| 1 | Purpose | 0:30 | 0:30 |
| 2 | Problem/use case | 0:55 | 1:25 |
| 3 | Solution | 0:45 | 2:10 |
| 4 | Architecture | 1:05 | 3:15 |
| 5 | Methodology | 0:55 | 4:10 |
| 6 | Reliability | 0:55 | 5:05 |
| 7 | Simulated performance | 0:45 | 5:50 |
| 8 | Human/judge results | 0:55 | 6:45 |
| 9 | Demo, including switching windows | 3:00 | 9:45 |
| 10 | Challenges/limits | 0:55 | 10:40 |
| 11 | Verified results/access | 0:50 | 11:30 |
| 12 | Conclusion | 0:30 | 12:00 |

## Before presenting — not part of the 12 minutes

- Start Docker and run `python3 scripts/run_demo.py` from the repository root well before recording. Never spend class time downloading/building images.
- Wait for `DEMO READY`. Open `http://127.0.0.1:8013/dashboard/`. Use the actual printed URL if you chose another port. Confirm fake/simulated mode; do not open the Gemini app on 8012.
- Copy the printed baseline and candidate short IDs onto a cue card, with dataset `portfolio-demo · v1`. Keep the printed report open privately if needed. Do not memorize total runs: history is preserved and counts change.
- Test one disposable UI dataset once, and rehearse the steps below. Use a different name during the presentation, e.g. `Class demo Nov17 take2`. A previously saved name/version with different cases will conflict.
- In Runs, leave the default one-case JSON intact. Do not type a large JSON example while presenting. Have a backup browser tab already on Compare with the preseeded runs, if you prefer.
- Keep the three screenshots in `reports/grader-demo-*.png` in your deck or a backup folder. Label them “Recorded successful rehearsal” if you use them. They show an earlier run, not your current live action.
- Turn off notifications, close unrelated tabs, keep passwords/private labels out of frame. Check microphone and text size. Record a short audio/screen test. Keep a local copy of the recording before uploading.
- Open the final PowerPoint once after export. Check screenshots, chart labels, notes, fonts and the template credits slide. Make links readable; make no assumption that Gemini imported a template just because you named it.

## Slide 1 — AgentEval (0:00–0:30)

“Hi everyone. My project is AgentEval, a test bench for AI application changes.

Imagine changing a chatbot's instructions and then wondering: did that help, or did I just break something that used to work? AgentEval runs saved questions, records the answers and helps compare versions. I’ll explain the design, show the evidence, and demonstrate the app without making paid AI calls.”

[Move on. Do not spend time listing every technology on the title slide.]

## Slide 2 — Problem and use case (0:30–1:25)

“Suppose a student is building a campus help bot. One version correctly answers a question about library hours. Would one correct answer convince you the whole bot works?”

[Two-second pause or quick show of hands; no extended audience discussion.]

“Probably not. One good answer is a nice screenshot, not a test strategy.

Changing the instructions might improve one answer but damage another. Answers can also sound convincing while adding facts that are not in the source material. The developer needs repeatable questions and a record of what changed.

This campus bot is an example use case, not a real deployment. AgentEval is mainly for developers and AI coursework when testing changes. It is not something every student needs to open every morning.”

## Slide 3 — Solution (1:25–2:10)

“AgentEval gives that developer a repeatable workflow.

First, save a dataset: questions, expected answers and supporting text. Second, run an evaluation. Third, inspect the answers and scores. Finally, compare the old run with the new one.

That comparison is called regression testing: checking that a change has not made existing behavior worse.

The app keeps the evidence so I don’t have to rely on remembering which screenshot looked better. It also separates execution success from answer quality: a run can finish correctly while its answers fail the quality checks.”

## Slide 4 — Architecture (2:10–3:15)

[Point to each stage of one diagram.]

“The browser is the control panel, built with React. It sends requests to the Python FastAPI backend, which validates the input.

PostgreSQL stores the dataset and a durable list of jobs. Durable means the list survives an application restart. A separate worker picks up jobs, generates answers, asks the judge to score them, and saves the results. The dashboard reads those saved results.

The queue is the to-do list; the worker actually does the homework.

I chose database-backed jobs so work and results could be tracked together without another queue service in this small local project. The trade-off is database contention to monitor.

There is also a retrieval path: documents are converted into numeric representations so relevant pieces can be found and supplied as context. That uses pgvector and is tested through the API and scripts, not a fifth dashboard tab.”

## Slide 5 — Methodology (3:15–4:10)

“Each test has a question, an expected answer and optional supporting context. The generator gets the question and context, but not the expected answer. Otherwise I would be handing it the answer key.

The judge checks three things: is the answer correct, does it answer the question, and is it supported by the context? Those are correctness, relevance and groundedness, scored from zero to two.

The normal pass rule requires full scores, plus exact text matching when that option is enabled. When there is no context, groundedness can be unavailable.

But an AI judge can also make mistakes. So I compared its decisions with separately supplied human decisions. These scores are checks under a rubric, not a scientific probability that an answer is true.”

## Slide 6 — Reliability (4:10–5:05)

“Quality is only useful if the evaluation actually finishes and its results are trustworthy.

Replaying the same compatible submission key returns the existing queued run instead of creating new work. A worker then receives a temporary reservation, called a lease. If it disappears, the work can become available again. An expired worker cannot later overwrite the accepted result; that is what the fencing check protects.

I also bound concurrency, attempts and deadlines rather than letting requests grow forever. A simple background task alone would not give this recovery behavior.

There is an important limit: a crash after an AI service receives a request can still lead to a repeated external call and another charge. I protect database acceptance; I do not claim exactly-once AI execution.”

## Slide 7 — Simulated performance (5:05–5:50)

“This chart is from a simulated workload through the real PostgreSQL queue. It is not Gemini speed.

For one thousand jobs, averaged over three repetitions per setting, one configured lane took 40.40 seconds and sixteen configured lanes took 13.07 seconds: a 3.09-times ratio of mean completion times.

Configured lanes are not the same as observed overlap: the maximum observed overlap in those sixteen-lane runs was five. This is also a different experiment from the separate multi-process sweep.

The practical lesson is that bounded concurrency improved this controlled workload. It does not mean adding workers always makes a real model faster.”

## Slide 8 — Human and judge results (5:50–6:45)

“The first judge prompt matched six out of ten human decisions. Four mistakes were false positives: it accepted responses containing instructions trying to influence the grader.

I revised the judge instructions and kept results separated by prompt version. The revised prompt matched ten development decisions and forty response-level validation decisions.

That is fifty responses, but only ten underlying questions, with overlap across phases. It is a small synthetic convenience sample, not proof of universal accuracy.

A separate pilot used five new synthetic questions and ten responses, judged three times. Each repetition matched all ten human decisions, and the binary decisions stayed stable. That tells me something about repeatability on that pilot—not that an AI judge can replace human judgment.”

## Slide 9 — Demo (6:45–9:45)

[Switch to the already-running browser. Use the relative timestamps below. The clicks and waiting time are included, not added later.]

| Demo clock | Click/action | Say this |
|---|---|---|
| 0:00–0:20 | Open **Overview**. Point to the simulated notice and counts. | “This is the running local app. Today it uses a deterministic simulated provider, so this demonstration makes no Gemini requests. These numbers come from stored results, including earlier rehearsals.” |
| 0:20–0:45 | Click **Runs**. Set **Name** to a unique short name; leave **Version** at `1` and default JSON unchanged. Click **Save dataset** once. | “This test has a question, an expected answer and context. I save the dataset first, so the same version can be evaluated again. In this example the source says Paris; it is deliberately simple so we can focus on the workflow.” |
| 0:45–1:05 | Confirm “Dataset saved.” The new dataset should be selected. Click **Submit run** once. | “Submit run saves the work in the queue. A background worker performs it. Saving a dataset and submitting a run are separate actions.” |
| 1:05–1:40 | Wait briefly for refresh, or click **Refresh**. Click the new short run ID. Scroll to **Evaluation details**. Point to completed job, attempts and answer. | “Completed means execution finished. Here the job completed in one attempt, and this answer also passed quality checks. Those are different facts. The explanation identifies the simulated check; this is not evidence of Gemini intelligence.” |
| 1:40–2:20 | Click **Compare**. Select **portfolio-demo · v1**. Choose the baseline/candidate short IDs from your cue card. Click **Compare runs**. | “I’m comparing two completed runs of the same dataset and compatible judge. PASS means the candidate stayed within the configured policy thresholds. Missing cases or different judges can instead produce INCONCLUSIVE. These example runs are equivalent; I’m showing the comparison workflow, not a new accuracy improvement.” |
| 2:20–2:45 | Click **Judge study**. Point to labels, pairs and scope. | “This page displays the recorded fifty-response study. It does not call Gemini when I open it. The small-sample limitation stays visible because fifty responses are not fifty independent questions.” |
| 2:45–3:00 | Return to slides. | “That completes the path from a saved test to a queued run, an inspected result and a comparison. Classmates can run this simulated path without an API key.” |

### Demo fallback — do not spend the whole talk troubleshooting

- If the new job is still pending after about 15 seconds: “This job is still waiting for a worker. I’ll use the completed rehearsal run so we can inspect the results.” Select `portfolio-demo` and a preseeded run. Do not claim the new run completed.
- If dataset save reports a conflict: use a new name once. If unresolved, use `portfolio-demo` and skip new submission. Do not delete or overwrite data.
- If Compare is disabled: select dataset, baseline and candidate in that order. Dataset changes reset comparison selections. If it says INCONCLUSIVE, read the reason; do not relabel it PASS. Use the known compatible preseeded pair.
- If the browser/API is unavailable: “The live local service is unavailable right now. These screenshots show my earlier successful clean-clone rehearsal. I’ll walk through that recorded result.” Show the labeled backup screenshots and continue within the same three minutes. Do not pretend screenshots are live execution.
- If the judge page is blank or missing: “The packaged report is unavailable in this environment; the committed report records the study.” Refer to the saved results slide.
- If you lose time: skip creating/submitting a new dataset and show preseeded results. This saves 45–60 seconds. Do not skip the simulated/live distinction or results limitations.

## Slide 10 — Challenges and limitations (9:45–10:40)

“The biggest model-evaluation challenge was a judge following grading instructions embedded in an answer. I strengthened the judge prompt and then reported development and validation separately; I did not hide the original mistakes.

For reliability, I used persisted jobs, leases and guarded writes, but external calls can still repeat after uncertainty.

A historical high-contention database run also produced lock timeouts. I added blocker and transaction timing capture and a controlled timeout test. Later runs did not reproduce the original event, so its root cause remains unresolved.

Finally, this is a local, single-owner project. Public multi-user hosting and offsite disaster recovery remain unverified. A documented build-tool dependency advisory also remains open. Passing tests is evidence, not a guarantee that every failure or security issue is solved.”

## Slide 11 — Verified results and access (10:40–11:30)

“The final clean-clone rehearsal passed 257 backend tests and the packaged browser workflow. Stop and resume preserved earlier runs, and both hosted CI workflows passed for the tested revision.

A separate six-document RAG study also received genuine human review, but its corpus is too small for broad accuracy claims.

Classmates can clone the repository and run the default demo with Python and local Docker, without a model key. Real Gemini mode is optional: they need their own compatible Gemini key and available quota, and requests may cost money. There is no key-entry button in this dashboard.

So the local demo is ready; that is different from a publicly hosted production service.”

## Slide 12 — Conclusion (11:30–12:00)

“AgentEval is a way to collect repeatable evidence before changing an AI application: save tests, run them reliably, inspect answers and compare results.

My main lesson was that testing the AI and testing the system around it are both necessary. The next steps are broader independent evaluation, investigating the database timeout on comparable hardware, and approved private hosting and recovery checks.

Thank you. I’m happy to take questions if we have time.”

## Questions you should be able to answer — outside the timed script

| Likely question | Plain answer |
|---|---|
| Why not just ask Gemini ten questions manually? | That is fine for an early check. Saved versions, repeated runs, job history and comparisons become useful when making changes and needing a record. |
| Is this another chatbot? | No. It tests answers from a configured provider. It does not train or provide a new foundation model. |
| Can it test any arbitrary chatbot URL? | Not through this current dashboard. It uses built-in fake/Gemini providers and a RAG target. An arbitrary external service needs an adapter; no universal integration is claimed. |
| Why use Gemini as both generator and judge? | It simplifies the integration, but shared-model mistakes can correlate. That is one reason human labels and future independent judges matter. |
| Did you prove 100% accuracy? | No. The observed agreement is limited to the disclosed reviewed samples. Prompt development also used the first failures. |
| Do the three repetitions prove determinism? | No. Ten binary decisions were stable in those three runs; other inputs, model updates, scores and explanations can differ. |
| Why PostgreSQL rather than Redis/Celery? | It keeps job/result transactions in one store for this small deployment. A separate broker is a valid alternative with extra operating complexity; PostgreSQL contention is a trade-off. |
| Why not an in-memory queue? | It loses pending work on process exit. Durable jobs support restart/recovery and inspection. |
| Is a PASS a good release decision? | It is one check under the chosen dataset and thresholds, not a complete release approval. A poor dataset can miss serious failures. |
| Is an external request executed exactly once? | No. A response can be lost after the provider executes; recovery may repeat it. Fencing governs accepted database writes, not external execution. |
| Are 257 tests 257 user scenarios? | They are automated checks across units/integration behavior. Test count is not a percentage of reliability or coverage. |
| Are all tests rerun by the demo command? | No. The launcher rehearses a narrow workflow/policy path. The full test suite is a separate verification step already recorded. |
| Can a student run this on their laptop? | On a supported setup with Python 3.12+ and local Docker. Initial downloads need internet. No key for fake mode; real Gemini needs their own eligible key/model/quota. Native Windows PowerShell is not supported; the documented Linux/WSL path needs a local Unix-socket engine. |
| Will it always be free? | Fake mode has no external model calls. Docker/system resources still have a cost, and provider billing/free-tier eligibility is not guaranteed. |
| What is retrieval? | Finding relevant pieces of supplied documents before answering. Numeric embeddings help compare text similarity; retrieval success alone does not prove the final answer is supported. |
| Where is the RAG interface? | API routes/scripts, not a dashboard tab. There is no document upload UI in this version. |
| Why use such simple demo questions? | They make queue/result/comparison mechanics easy to inspect. Real evaluation needs representative domain data and expert judgments; simple fake questions do not establish AI quality. |
| What do you still need to improve? | Representative data, independent reviews, timeout attribution, deployment/recovery validation and dependency follow-up. |
| Is it secure? | It has scoped controls and local/private preparation, but no comprehensive security certification or public multi-user readiness claim. |
| Did you use AI coding help? | Answer honestly about the assistance you used and your school's disclosure rules. Do not claim all code or human decisions were written unaided if that is untrue. Be ready to explain the decisions and reproduce the demo yourself. |

## Recording and submission

The supplied instructions say: record, upload to YouTube or Google Drive, post the shareable link in Canvas discussion, and upload the PowerPoint in advance. Verify the actual deadlines and detailed Canvas instructions yourself. Test the recording link using another account or an appropriate signed-out view, following your course privacy rules. Ensure the grader can view it without an access request. Test audio and screen readability. Preserve the Slidesgo credits and repository/report references. Do not start recording with API keys or raw reviewer notes visible.
