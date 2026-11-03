# Regression policies and CI

POST /comparisons accepts baseline_run_id, candidate_run_id and an optional policy. GET /runs/{id}/comparison-input exports the normalized input for the same command-line checker:

```
.venv/bin/python -m agenteval.regression --baseline baseline.json --candidate candidate.json --output artifacts/regression.json
```

Exit codes: PASS=0, FAIL=1, INCONCLUSIVE=2. Both non-pass outcomes block an automated gate; they mean different things. Dataset identity/case count, judge provider/model, rubric and simulation mode must match. Every case must be paired and both runs must have completed execution. Different generation prompts are allowed. Because the initial provider uses the same model for generation and judgment, comparing different models is currently inconclusive rather than confounding a judge change with target quality.

Default thresholds allow at most 0.05 absolute pass-rate loss and 0.25 mean correctness loss. These are configurable demonstration policies, not calibrated statistical significance tests. Minimum case count defaults to one for local smoke checks; choose a meaningful dataset and repeat noisy live evaluations before using deployment gates. Scores are ordinal, not probabilities. Latency and token-ratio gates are optional; missing token usage makes an enabled token gate inconclusive. Latency is generation plus judge execution time, not queue wait or end-to-end completion time.

The deterministic CI gate runs the actual evaluation service with three controlled fake-provider facts and compares it to explicit expected fixture outcomes. Command: `.venv/bin/python -m agenteval.regression --demo-gate`. This is a simulated application regression gate, not a live Gemini quality study. GitHub Actions also runs unit/database tests and uploads machine-readable reports. Its hosted execution is not verified from this environment.

The separate workflow_dispatch live-judge workflow is opt-in, validates a 1–10 example limit, requires repository secret GEMINI_API_KEY and variable AGENTEVAL_MODEL, and never runs on fork pull requests. Cloud environment secrets do not automatically configure GitHub repository secrets. No paid calls were made in routine verification.

Threshold comparisons tolerate only 1e-12 floating-point rounding at an equality boundary; this is numerical hygiene, not a statistical margin. A 20-case suite with exactly one allowed failure at a 0.05 loss threshold passes rather than failing from binary-float representation.
