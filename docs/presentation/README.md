# Final presentation kit

Prepared for the supplied CSCI 310 final-presentation instructions: 10–15 minutes, covering problem, methodology, results/demo, challenges and conclusion. Target **12:00 including 3:00 of demo**, leaving room for normal pauses and potentially short questions within a 15-minute slot. Confirm whether Q&A counts toward your professor's limit. The referenced original Word document and additional Canvas requirements were not independently supplied/read; this kit follows the rubric text provided in the conversation.

## Use these in this order

1. [App user guide](APP_USER_GUIDE.md): learn the four tabs and rehearse their controls before learning the speech.
2. [Gemini prompt](GEMINI_PROMPT.md): copy the prompt below its divider. Supply the downloaded template and real screenshots if your Gemini interface accepts them. No Gemini request has been made by creating this kit.
3. [Presenter script and click-by-click demo](PRESENTER_SCRIPT.md): rehearse with a stopwatch; actions and browser switching are included in the budget.

These files are presentation instructions, not an already-generated PowerPoint. Review any generated deck for incorrect numbers, invented features or missing caveats before submitting it.

## Slidesgo template choice

**Recommended: [Sunset Palette Portfolio](https://slidesgo.com/theme/sunset-palette-portfolio).** The page currently lists it as a free editable template with PowerPoint/Google Slides options and editable charts/graphics. Its sunset/cream/gradient direction matches the app and can accommodate screenshots and architecture diagrams. My recommendation is to use its simplest layouts and reduce decorative elements on evidence slides. This is a project-specific design judgment, not a claim that the template was downloaded or applied here.

**Quieter alternative: [Simple Terracota Palette Portfolio](https://slidesgo.com/theme/simple-terracota-palette-portfolio).** Also currently listed as free; its warm terracotta/cream palette and editable visual resources suit a restrained technical talk. It lists 25 layouts; use only the layouts you need, not all 25 as presentation slides.

**Academic alternative: [Soft Gradients Thesis Defense](https://slidesgo.com/theme/soft-gradients-thesis-defense).** Use if you prefer a research-defense structure, recoloring it to the app palette.

Template pages were checked on 2026-11-17. Download access/account conditions can change. For free use, Slidesgo instructs users to retain the credits slide. Keep the template's actual credits and comply with its downloaded terms. Use 12 main content slides and keep credits/evidence/glossary as unpresented appendices. A template link alone does not make Gemini import or edit that file.

### Practical download/customization steps

1. Open the recommended page. Use its PowerPoint download option, or Google Slides option if that is where you edit. Sign in only if the site requires it; do not buy anything just to follow this plan.
2. Keep a clean original template copy. Duplicate your working copy.
3. Pick cover, diagram, chart, screenshot and simple text layouts; remove unrelated portfolio sections and stock content. Retain credits.
4. Apply the app palette: peach `#FBF1EB`, plum `#382936`, burnt orange `#B4492E`, coral `#CC7855`, cream `#FFFAF6`. Keep body text dark on a light background. Small light text over an orange gradient will be hard to read on a projector.
5. Put the script into speaker notes. Do not paste it all into slide bodies. One key idea and a visual per slide; roughly 25–40 visible words on most slides.
6. Add the real app screenshots below and the editable benchmark bar chart with its simulated-workload label.
7. Open the exported `.pptx` in your actual presentation software and rehearse transitions/screensharing. Check that notes exist; slide-generation tools do not always preserve them.

## Evidence and assets

| Claim/asset | Repository source |
|---|---|
| Full clean-clone/demo acceptance and 257 backend checks | [Final verification](../../reports/grader-demo-final-verification.json) |
| Original completed results retained after restart | [First rehearsal](../../reports/grader-demo-first-run.json), [resume](../../reports/grader-demo-resume.json) |
| Overview screenshot | [Real rehearsal image](../../reports/grader-demo-overview.png) |
| Run details/jobs/answers screenshot | [Real rehearsal image](../../reports/grader-demo-run-details.png) |
| Comparison screenshot | [Real rehearsal image](../../reports/grader-demo-comparison.png) |
| 40.40 s versus 13.07 s; 3.09x simulated ratio | [Historical benchmark](../BENCHMARK_REPORT.md) |
| Original and improved judge studies | [Study methodology](../HUMAN_LABELING.md), [50-pair report](../../reports/judge_validation.json) |
| Five-question/three-repetition pilot | [Completion](../../reports/new-question-live-completion.json) |
| Eight-answer RAG human review | [Completion](../../reports/rag-human-review-completion.json) |
| Scope/security/dependency/timeout limits | [Known limitations](../KNOWN_LIMITATIONS.md), [lock review](../LOCK_CONTENTION_REVIEW.md) |
| Clone/run steps and supported environment | [README](../../README.md) |

Numbers belong to these recorded runs, not a fresh benchmark performed for the presentation. Do not convert a test count into a reliability percentage, a simulated timing into Gemini throughput, or small-sample agreement into universal accuracy. Screenshots are recorded evidence unless you are actually showing the running browser.

## Practical timing and recording

Use the script's 12-minute schedule. At slide 9, switch windows by 6:45 and return by 9:45. If new submission is delayed, immediately use the preseeded runs rather than troubleshooting. At 11:30 begin the conclusion. If running behind, skip the new-dataset part of the demo and shorten the benchmark commentary; do not remove the limitations or pretend an incomplete job passed. Aim to complete the talk around 12 minutes; do not intentionally fill the entire 15 minutes before questions.

Check recording audio, screen readability, slide export and share permissions in advance. Follow the professor's supplied requirement to upload the PowerPoint in advance, post the shareable recording link in Canvas discussion, and use YouTube or Google Drive for the recording. Verify exact deadlines/additional requirements in Canvas. Nobody else can supply your own presentation delivery or peer feedback. The script includes likely questions, but it cannot cover every possible question; understand the architecture and practice in the running app.
