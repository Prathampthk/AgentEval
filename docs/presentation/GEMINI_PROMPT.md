# Paste this prompt into Gemini

Before pasting: download the Slidesgo template and attach it if your Gemini interface supports presentation-file input. Also attach `reports/grader-demo-overview.png`, `reports/grader-demo-run-details.png` and `reports/grader-demo-comparison.png`. Do not attach `.local`, credentials or private human-label files. If Gemini cannot edit the template or produce an actual PowerPoint, ask for slide content and speaker notes, then place them in the template yourself. A text answer is not a finished PPTX.

Copy everything below the line.

---

Create my CSCI 310 FINAL project presentation about AgentEval. Use beginner-friendly English, accurate engineering claims and a practical demonstration. This is a final presentation, not a proposal or a sales pitch.

OUTPUT
- Exactly 12 main slides, in the order and timing below, plus three unpresented appendices (glossary/architecture details; evidence/sources; Slidesgo credits). Appendices are for questions, not the timed talk.
- Target exactly 12 minutes INCLUDING a 3-minute live demo on slide 9. The professor's allowed range is 10–15 minutes. Do not create 12 minutes of narration plus a separate demo.
- For each slide: title, actual concise slide text, specific visual layout and speaker notes in ordinary spoken English. Put the full script in notes, not on the slide. Include transitions, time budget and cumulative time.
- If file generation is supported, produce an editable PowerPoint with editable chart/diagram objects and speaker notes. Otherwise return a complete slide-by-slide specification and clearly say no PowerPoint was generated.
- Do not claim you used a supplied file/template or screenshot unless it was actually supplied and used. For missing assets put clearly labeled placeholders. Do not invent screenshots or results.

GRADING AND CONTENT
Rubric supplied by my professor: content/understanding 60, organization/clarity 20, presentation/slides 15, time management 5. Final presentation must cover problem, methodology, results/demo, major challenges, responses to challenges, and conclusion. Include design choices and limitations. A proposal timeline is not required here; show completed engineering phases only if useful in the appendix, without inventing dates.

DESIGN
Use the attached Slidesgo Sunset Palette Portfolio template if provided, or use its general warm sunset direction without pretending to have imported it:
https://slidesgo.com/theme/sunset-palette-portfolio
Alternative: https://slidesgo.com/theme/simple-terracota-palette-portfolio
Retain required template credits. Prefer 16:9, peach #FBF1EB, plum #382936, burnt orange #B4492E, coral #CC7855 and pale cream #FFFAF6. Large readable titles 32–40 pt, body 22–26 pt, no tiny caveats. Keep backgrounds calm behind charts/screenshots. Use dark plum text on light surfaces. One main idea per slide, about 25–40 visible words excluding small source labels. No robot clipart, fake testimonials, decorative dashboards or stock photos of people pointing at screens. Favor one workflow diagram, real screenshots and one simple bar chart. Use minimal transitions; no automatic slide advance during the demo.

REAL USE CASE
AgentEval is a local developer testing tool, not a new general chatbot, not an everyday app for every student, and not a trained foundation model. A developer changing a support chatbot's prompt needs to rerun the same questions and compare old/new answers. For example, a fictional campus help bot should answer from supplied library policy rather than invent facts. That is a possible application, not an actual campus deployment or tested customer case. AgentEval keeps versioned tests, queues work, records answers/scores and compares compatible runs. Human review remains necessary.

VERIFIED FACTS — use exactly these distinctions
1. React/TypeScript dashboard; FastAPI Python backend; PostgreSQL for stored datasets/runs/jobs/results; background workers with leases/retries; Docker Compose packaging. Optional Gemini generation/judgment; pgvector-based retrieval target. Generation does not receive the expected-answer field. The judge receives the expected answer, context and generated answer.
2. One dataset = a versioned collection of questions, expected answers and supporting context. One run = an evaluation of that dataset with a configuration. A job is one queued test case. Answer generation and judging are sequential operations within an evaluation.
3. Correctness = is the answer right? Relevance = does it answer the question? Groundedness = is it supported by context? Rubric scores are 0–2. Normal pass requires correctness=2, relevance=2, groundedness=2 when context exists, and exact-match success if requested. Without context groundedness may be unavailable. These are rubric scores, not calibrated probabilities.
4. Submission keys avoid creating a new queued run when the same compatible submission is replayed. A worker lease is a temporary reservation. Fencing prevents an expired worker's stale result from being accepted. External calls can still repeat after crashes or uncertainty; never claim exactly-once external execution or no duplicate charges.
5. Regression comparison yields PASS, FAIL or INCONCLUSIVE. INCONCLUSIVE can mean incomplete cases or incompatible judge configurations. Thresholds are demonstration policies, not statistical significance. A completed run can contain quality failures.
6. Latest full clean-clone verification: 257 backend tests passed, one packaged Chromium browser workflow passed, queue replay/fake RAG smoke passed, stop/resume preserved the first two runs and four results. Both hosted CI workflows passed at tested revision 9bd721240ff9d6e402cebd8b27bee1da80aa2e26. This is recorded evidence, not a claim that tests cover every failure mode. The fresh checkout used available Docker build cache, not a cache-cold computer.
7. Historical SIMULATED throughput experiment: 1,000 jobs per configuration, three repetitions each, 1 versus 16 configured asynchronous lanes. Mean completion time 40.40 s versus 13.07 s, ratio 3.09x. Observed peak overlap in configured-16 variants was five. This is not 16 separate processes, not Gemini speed and not live-provider throughput. Label chart clearly “Simulated workload; lower time is better.”
8. Human/judge study: v1 baseline matched 6/10 decisions and produced four false positives on instruction-injection responses. Candidate-v2 matched 10/10 development responses and 40/40 response-level validation responses: 50 responses across ten overlapping underlying questions, one human reviewer, synthetic convenience sample. Prompt development used observed baseline failures. This is not 100% general accuracy or fifty independent questions.
9. Separate new-question repeatability pilot: five new synthetic questions, two responses each, three repetitions = 30 attempted/saved Gemini judgments. Each repetition matched all ten frozen human decisions; all ten binary decisions stayed stable. Not thirty independent examples and not evidence of identical scores/explanations.
10. Separate live RAG study: six synthetic documents/eight questions, expected documents retrieved for six answerable questions at K=3. Genuine human review marked 6/6 answerable responses/citations supported and 2/2 unknown responses appropriate abstentions. Small synthetic fixture; not broad retrieval/citation accuracy.
11. Demo: `python3 scripts/run_demo.py`, then http://127.0.0.1:8013/dashboard/. Needs Git, Python 3.12+ and local Docker/Compose v2+ on supported macOS/Linux or WSL2 Linux with local Unix-socket Docker. Initial build needs internet. No API key or host Node/PostgreSQL/Python-package install required for this launcher. Native PowerShell/remote TCP Docker are not supported. The launcher seeds two queued runs/two cases each and synthetic policy scenarios.
12. The default provider is fake: deterministic placeholder responses and simple checking, not semantic intelligence. Prompt changes in fake mode are not evidence of real prompt quality. The current four tabs are Overview, Runs, Compare and Judge study. RAG ingestion and retrieval are API/script workflows; there is no RAG dashboard tab or API-key-entry field.
13. Optional real Gemini mode uses `python3 scripts/run_gemini.py --model gemini-3.1-flash-lite`, with the user's own securely entered usable Gemini key/model. Eligibility, quota and possible charges depend on their provider project. It is not guaranteed free. No OpenAI/other-provider support is claimed. Do not run Gemini live in this presentation. Existing authorized research allowances are consumed.
14. Limitations: unresolved historical PostgreSQL lock-timeout cause; public deployment, tenant isolation and offsite recovery unverified; single-host attempt/rate/concurrency controls are not a monetary/account-wide ledger. A build-tool picomatch advisory remains documented with no published patch at final verification; production frontend dependency audit reported zero findings. Do not call the app production-ready, perfectly secure or foolproof.

SLIDE PLAN — total 12:00, including demo
1. AgentEval — 0:30 (end 0:30). Purpose and subtitle “A test bench for AI application changes.”
2. Problem and use case — 0:55 (end 1:25). A fictional campus help bot; “Would one correct answer convince you?” Brief audience question, no long discussion.
3. Proposed solution — 0:45 (end 2:10). Versioned questions → run → inspect → compare. Developers/AI coursework use it when changing an app, not necessarily daily.
4. Architecture — 1:05 (end 3:15). Draw browser → API → PostgreSQL queue → worker → fake/Gemini → stored results → dashboard. Add optional documents → embeddings/pgvector → retrieved context as a small side path. Explain terms in notes.
5. Evaluation methodology — 0:55 (end 4:10). Expected answer kept from generator; judge checks answer/reference/context using 0–2 rubric. Human review checks judge.
6. Reliability — 0:55 (end 5:05). Replayed submission, temporary reservation, guarded result acceptance; one plain-language analogy. Visible caveat: duplicate external calls remain possible.
7. Simulated performance — 0:45 (end 5:50). Two-bar chart: 40.40 s and 13.07 s. Visible workload/scope and observed-overlap caveat; never imply real Gemini acceleration.
8. Human/judge results — 0:55 (end 6:45). Baseline 6/10 → candidate development10/10 + response-validation40/40; sample caveat visible. Small optional annotation: new five-question pilot10/10 each of three repetitions, stable binary decisions. No generalized accuracy claim.
9. Live local demo — 3:00 (end 9:45). Slide says “Simulated provider • zero model calls.” Switch to prepared browser: Overview, Runs, submit one prepared single-case dataset, inspect answer/job, Compare two preseeded runs, Judge study. Preseeded runs and screenshots are fallback. Do not perform installation, key entry, crash injection or a live Gemini request on stage.
10. Challenges and limitations — 0:55 (end 10:40). Judge followed answer-side grading instructions → stronger structured prompt and separately reported validation. Crash uncertainty → leases/fencing, external duplication still possible. Historical database timeout → instrumentation; cause still unresolved. Brief hosting/security scope.
11. Verified results and access — 0:50 (end 11:30). 257 backend checks, browser workflow and preserved restart history. Students can clone/run fake demo with no key; optional Gemini needs their own compatible key and quota. Small RAG evidence footnote or appendix, not a crowded results slide.
12. Conclusion — 0:30 (end 12:00). Repeatable evidence before changing an AI application; local demo ready; broader tests/approved hosting remain. Invite questions if time permits.

SPEAKING STYLE
Keep humor sparse and friendly: “One good answer is a nice screenshot, not a test strategy” or “The queue is the to-do list; the worker actually does the homework.” Do not joke about failures you cannot explain. Explain jargon immediately. Keep the audience question to a show of hands or a two-second pause. Avoid “revolutionary,” “seamless,” “leverage,” and sales claims.

NOTES AND SOURCES
Put repository report references in relevant slide notes, with a readable short source label on metric slides:
- https://github.com/Prathampthk/AgentEval
- reports/grader-demo-final-verification.json (tested revision and checks)
- docs/BENCHMARK_REPORT.md and reports/benchmark.json (simulated benchmark)
- reports/judge_validation.json and reports/judge-baseline-v1-agreement.json
- reports/new-question-live-completion.json (repeatability pilot)
- reports/rag-human-review-completion.json
- docs/KNOWN_LIMITATIONS.md
Use real supplied screenshots, crop to useful content, retain “simulated” evidence labels. Put full references in the evidence appendix. Do not invent a customer, deployment, metric, test, feature, citation or date.
