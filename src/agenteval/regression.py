"""Compatible-run quality comparison and a shared local/CI regression command."""

import argparse
import asyncio
import json
import math
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from agenteval.domain import EvaluationRequest, StrictModel
from agenteval.providers import FakeProvider
from agenteval.service import evaluate


class ComparisonCase(StrictModel):
    test_case_id: str
    passed: bool = Field(strict=True)
    correctness: float = Field(ge=0, le=2, allow_inf_nan=False)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)
    tokens: int | None = Field(default=None, ge=0)


class ComparisonRun(StrictModel):
    dataset_id: str
    expected_cases: int = Field(ge=1)
    status: Literal["RUNNING", "COMPLETED", "FAILED", "CANCELED"]
    judge_provider: str
    judge_model: str
    rubric_version: str
    judge_prompt_version: str = "v1"
    judge_prompt_sha256: str | None = None
    simulated: bool
    results: list[ComparisonCase]

    @model_validator(mode="after")
    def unique_cases(self):
        if len({r.test_case_id for r in self.results}) != len(self.results):
            raise ValueError("Duplicate case identifiers")
        if len(self.results) > self.expected_cases:
            raise ValueError("More results than expected cases")
        return self


class RegressionPolicy(StrictModel):
    max_pass_rate_drop: float = Field(default=0.05, ge=0, le=1, allow_inf_nan=False)
    max_correctness_drop: float = Field(default=0.25, ge=0, le=2, allow_inf_nan=False)
    min_cases: int = Field(default=1, ge=1)
    max_latency_ratio: float | None = Field(default=None, gt=1, allow_inf_nan=False)
    max_token_ratio: float | None = Field(default=None, gt=1, allow_inf_nan=False)


def comparison_input(run, expected_cases):
    rows = []
    for result in run.results:
        counts = [
            result.generation_usage.input_tokens,
            result.generation_usage.output_tokens,
            result.judge_usage.input_tokens,
            result.judge_usage.output_tokens,
        ]
        rows.append(
            ComparisonCase(
                test_case_id=result.test_case_id,
                passed=result.passed,
                correctness=result.judgment.correctness,
                latency_ms=result.generation_latency_ms + result.judge_latency_ms,
                tokens=sum(counts) if all(n is not None for n in counts) else None,
            )
        )
    return ComparisonRun(
        dataset_id=str(run.dataset_id),
        expected_cases=expected_cases,
        status=run.status,
        judge_provider=run.provider,
        judge_model=run.model,
        rubric_version=run.rubric_version,
        judge_prompt_version=run.configuration.get("judge_prompt_version", "v1"),
        judge_prompt_sha256=run.configuration.get("judge_prompt_sha256"),
        simulated=run.simulated,
        results=rows,
    )


def exceeds(value, limit):
    return value > limit and not math.isclose(value, limit, rel_tol=1e-12, abs_tol=1e-12)


def compare(baseline, candidate, policy=None):
    policy = policy or RegressionPolicy()
    incompatible = [
        key
        for key in (
            "dataset_id",
            "expected_cases",
            "judge_provider",
            "judge_model",
            "rubric_version",
            "judge_prompt_version",
            "judge_prompt_sha256",
            "simulated",
        )
        if getattr(baseline, key) != getattr(candidate, key)
    ]
    reasons = []
    if incompatible:
        reasons.append("Incompatible " + ", ".join(incompatible))
    left = {r.test_case_id: r for r in baseline.results}
    right = {r.test_case_id: r for r in candidate.results}
    if baseline.status != "COMPLETED" or candidate.status != "COMPLETED":
        reasons.append("Run execution is incomplete or failed")
    if (
        set(left) != set(right)
        or len(left) != baseline.expected_cases
        or len(right) != candidate.expected_cases
    ):
        reasons.append("Missing or unpaired cases")
    if len(left) < policy.min_cases:
        reasons.append("Insufficient paired cases")
    output = {
        "outcome": "INCONCLUSIVE",
        "paired_cases": len(set(left) & set(right)),
        "reasons": reasons,
        "policy": policy.model_dump(),
        "simulated": baseline.simulated or candidate.simulated,
        "metrics": {},
    }
    if reasons:
        return output
    n = len(left)
    metrics = {
        "baseline_pass_rate": sum(r.passed for r in left.values()) / n,
        "candidate_pass_rate": sum(r.passed for r in right.values()) / n,
        "baseline_correctness": sum(r.correctness for r in left.values()) / n,
        "candidate_correctness": sum(r.correctness for r in right.values()) / n,
        "baseline_latency_ms": sum(r.latency_ms for r in left.values()) / n,
        "candidate_latency_ms": sum(r.latency_ms for r in right.values()) / n,
    }
    if policy.max_token_ratio is not None:
        if any(r.tokens is None for r in [*left.values(), *right.values()]):
            output["reasons"] = ["Token policy requested but usage is missing"]
            return output
        metrics["baseline_tokens"] = sum(r.tokens for r in left.values()) / n
        metrics["candidate_tokens"] = sum(r.tokens for r in right.values()) / n
    failures = []
    if exceeds(
        metrics["baseline_pass_rate"] - metrics["candidate_pass_rate"], policy.max_pass_rate_drop
    ):
        failures.append("Pass-rate regression")
    if exceeds(
        metrics["baseline_correctness"] - metrics["candidate_correctness"],
        policy.max_correctness_drop,
    ):
        failures.append("Correctness regression")
    for name, ratio in [
        ("latency_ms", policy.max_latency_ratio),
        ("tokens", policy.max_token_ratio),
    ]:
        if ratio is not None and exceeds(
            metrics["candidate_" + name], metrics["baseline_" + name] * ratio
        ):
            failures.append(name + " regression")
    output.update(outcome="FAIL" if failures else "PASS", reasons=failures, metrics=metrics)
    return output


async def demo_gate():
    rows = []
    for index, answer in enumerate(["Paris", "4", "Mars"]):
        result = await evaluate(
            EvaluationRequest(
                dataset_name="ci-demo",
                dataset_version="1",
                test_case_id=str(index),
                question="Return the supplied fact",
                context=answer,
                expected_answer=answer,
                exact_match=True,
            ),
            FakeProvider(),
        )
        rows.append(
            ComparisonCase(
                test_case_id=str(index),
                passed=result.passed,
                correctness=result.judgment.correctness,
                latency_ms=0,
            )
        )
    common = dict(
        dataset_id="ci-demo-v1",
        expected_cases=3,
        status="COMPLETED",
        judge_provider="fake",
        judge_model="context-echo-v1",
        rubric_version="v1",
        simulated=True,
    )
    expected = [
        ComparisonCase(test_case_id=str(i), passed=True, correctness=2, latency_ms=0)
        for i in range(3)
    ]
    return compare(ComparisonRun(**common, results=expected), ComparisonRun(**common, results=rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline")
    parser.add_argument("--candidate")
    parser.add_argument("--output", default="artifacts/regression.json")
    parser.add_argument("--demo-gate", action="store_true")
    args = parser.parse_args()
    if args.demo_gate:
        result = asyncio.run(demo_gate())
    else:
        if not args.baseline or not args.candidate:
            parser.error("baseline and candidate are required unless --demo-gate is used")
        baseline = ComparisonRun.model_validate_json(Path(args.baseline).read_text())
        candidate = ComparisonRun.model_validate_json(Path(args.candidate).read_text())
        result = compare(baseline, candidate)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    raise SystemExit({"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2}[result["outcome"]])


if __name__ == "__main__":
    main()
