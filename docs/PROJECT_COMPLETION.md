# Project completion and remaining acceptance

The local portfolio project is ready to demonstrate. Run `python3 scripts/run_demo.py` with Python 3.12+ and local Docker, then follow [the five-minute walkthrough](DEMO.md). No API key is needed. Present the simulated workflow separately from the recorded live studies.

## Completed portfolio scope

- Versioned datasets, persistent results and durable queued execution with bounded workers.
- Controlled retry, crash, database interruption, lease fencing and restart checks.
- Regression PASS/FAIL/INCONCLUSIVE policies and packaged dashboard browser verification.
- Repeated one-command fake demo with preserved history.
- Fifty genuine human judge decisions with separately recorded live predictions and prompt provenance.
- Small live retrieval study with all eight genuine human reviews completed.
- Provider-independent private Ubuntu/Docker templates, owner authentication, local TLS, persistent request admission and encrypted local restore procedures.

[DELIVERABLES.md](DELIVERABLES.md) links evidence for each item. Earlier reports describe their own historical state; completion does not change their measurements.

## Remaining work by acceptance boundary

| Work | What is needed next | Completion evidence |
|---|---|---|
| New-question judge generalization and repeatability | Agree independent questions/ground truth, blind genuine human review, freeze a study plan and approve a new attempted-request allowance before collection | Report all attempted calls, failures, usage availability, question-level split and repeated-run disagreement; retain negative results |
| Broader RAG quality | Agree representative corpus/questions and human evidence rubric; approve collection allowance | Retrieval coverage plus genuine answer/citation/abstention reviews, disclosed sample and reviewer limits |
| Historical PostgreSQL timeout attribution | Original or comparable hardware and actual recurrence | Retained positive control and uninjected traces correlated with blocker/client/WAL timing; non-recurrence alone does not resolve cause |
| Actual private server | Select provider/host and explicitly approve provisioning | Follow private runbook on Ubuntu 24.04, verify owner access, TLS, migrations, worker restart and bounded fake workflow remotely |
| Offsite disaster recovery | Select encrypted destination, retention and separately protected key recovery | Restore on a separate host from offsite copies, verify data/ledger and record measured recovery times; never reset spent allowance automatically |
| Ongoing operations | Provisioned private host and chosen monitoring/retention policy | Exercise alerts, backup scheduling, dependency updates and recovery runbook on that host |

All earlier live collection allowances are consumed. Free-tier eligibility and remaining project quota are not established by a successful request. Admission counters are separate from provider billing. No new provider calls, paid resources or live deployment follow automatically from this checklist.

## Prepared next evaluation

The [new-question pilot](NEW_QUESTION_STUDY.md) now has a frozen offline plan and an empty genuine-human review packet: ten synthetic responses across five new questions, with three repetitions proposed. No labels or provider calls were generated. The dedicated collector/analysis is implemented and offline-tested. Genuine human review is now complete: ten validated decisions (five pass, five fail), preserved privately with [aggregate provenance](../reports/new-question-human-review-completion.json). The separately authorized live collection subsequently completed: three repetitions each matched all ten decisions, with all ten binary decisions stable. See [completion evidence](../reports/new-question-live-completion.json). The thirty-attempt allowance is consumed. Broader representative evaluation remains distinct from this synthetic pilot.

## Public service is a separate scope

Multi-user authorization, tenant isolation, public ingress/abuse controls, cross-host quotas, comprehensive security review and availability/recovery targets are not part of the private single-owner demo. Define and authorize that scope before implementing or publishing it. No exactly-once external execution claim is justified.
