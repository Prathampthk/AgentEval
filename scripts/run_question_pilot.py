"""Validate a frozen pilot, or explicitly collect bounded sequential repetitions."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import runpy
from pathlib import Path

from agenteval.judge_validation import HumanLabel, agreement
from agenteval.runtime import provider_context

ROOT = Path(__file__).resolve().parents[1]
collect = runpy.run_path(str(ROOT / "scripts/judge_examples.py"))["collect"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plan(folder):
    plan = json.loads((folder / "plan.json").read_text())
    if digest(folder / "fixture.json") != plan["fixture_sha256"]:
        raise ValueError("Frozen fixture hash mismatch")
    source = json.loads((folder / "fixture.json").read_text())
    by_id = {r["example_id"]: r for r in source}
    ids = plan["example_ids"]
    if len(by_id) != len(source) or len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise ValueError("Plan IDs do not match fixture")
    if plan["proposed_repetitions"] != 3 or not 1 <= len(source) <= 10:
        raise ValueError("Pilot requires three repetitions of at most ten responses")
    if plan["proposed_judge_operations"] != 3 * len(source):
        raise ValueError("Invalid operation count")
    return plan, [by_id[key] for key in ids]


def validate_labels(path, rows):
    labels = [HumanLabel.model_validate(r).model_dump() for r in json.loads(path.read_text())]
    ids = [r["example_id"] for r in labels]
    if len(set(ids)) != len(ids) or set(ids) != {r["example_id"] for r in rows}:
        raise ValueError("Labels must cover each frozen response exactly once")
    if any(
        r["human_pass"] is None or not (r["labeler"] or "").strip() or r["rubric_version"] != "v1"
        for r in labels
    ):
        raise ValueError("Complete genuine attributed v1 labels are required")
    return labels


def analyze(rows, labels, repetitions):
    if len(repetitions) != 3:
        raise ValueError("Three complete repetitions required")
    ids = {r["example_id"] for r in rows}
    configurations = set()
    for predictions in repetitions:
        keys = [r["example_id"] for r in predictions]
        if len(keys) != len(set(keys)) or set(keys) != ids:
            raise ValueError("Each repetition must cover the exact frozen IDs")
        for r in predictions:
            if type(r.get("passed")) is not bool or type(r.get("simulated")) is not bool:
                raise ValueError("Strict prediction decisions and simulation flags required")
            configurations.add(
                tuple(
                    r.get(k)
                    for k in (
                        "provider",
                        "model",
                        "simulated",
                        "judge_prompt_version",
                        "judge_prompt_sha256",
                    )
                )
            )
    if len(configurations) != 1 or any(v is None for v in next(iter(configurations))):
        raise ValueError("One fully identified provider/model/prompt configuration required")
    maps = [{r["example_id"]: r["passed"] for r in rep} for rep in repetitions]
    changed = sorted(key for key in ids if len({rep[key] for rep in maps}) > 1)
    return {
        "status": "SIMULATED_REHEARSAL" if next(iter(configurations))[2] else "MEASURED_PILOT",
        "distinct_questions": len({r["question"] for r in rows}),
        "responses_per_repetition": len(rows),
        "repetition_reports": [agreement(rows, labels, rep) for rep in repetitions],
        "decision_changes_across_repetitions": changed,
        "stable_response_count": len(ids) - len(changed),
        "limitation": "Synthetic five-question pilot; repeated predictions are not independent samples. Stability concerns binary decisions, not score or explanation identity.",
    }


def write_new(path, value):
    with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as file:
        file.write(json.dumps(value, indent=2) + "\n")


async def execute(folder, output, *, live=False, authorized_attempts=0, delay=13):
    plan, rows = load_plan(folder)
    if not live:
        return {
            "status": "PLAN_VALIDATED_NO_CALLS",
            "proposed_attempts": 3 * len(rows),
            "fixture_sha256": plan["fixture_sha256"],
        }
    if authorized_attempts != 3 * len(rows) or os.getenv("AGENTEVAL_PROVIDER") != "gemini":
        raise ValueError(
            "Explicit exact attempted-request allowance and Gemini configuration required"
        )
    if not math.isfinite(delay) or not 0 <= delay <= 60:
        raise ValueError("Invalid pacing")
    label_path = folder / "human_labels.json"
    labels = validate_labels(label_path, rows)
    label_bytes = label_path.read_bytes()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    snapshot = output / "human_labels.frozen.json"
    with open(snapshot, "xb", opener=lambda p, flags: os.open(p, flags, 0o600)) as file:
        file.write(label_bytes)
    snapshot.chmod(0o400)
    labels = validate_labels(snapshot, rows)
    write_new(
        output / "provenance.json",
        {
            "fixture_sha256": plan["fixture_sha256"],
            "labels_sha256": digest(snapshot),
            "authorized_attempts": authorized_attempts,
            "automatic_retries": False,
            "scope": "Private single-invocation ceiling; failed attempts are not refunded",
        },
    )
    repetitions = []
    async with provider_context(judge_prompt_version="candidate-v2") as provider:
        for index in range(3):
            if index:
                await asyncio.sleep(delay)
            repetitions.append(
                await collect(
                    provider, rows, output / f"repetition-{index + 1}.json", delay_seconds=delay
                )
            )
    report = analyze(rows, labels, repetitions)
    write_new(output / "analysis.json", report)
    return {"status": report["status"], "completed_repetitions": 3}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, default=ROOT / "artifacts/judge-new-questions")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--authorized-attempts", type=int, default=0)
    parser.add_argument("--delay-seconds", type=float, default=13)
    args = parser.parse_args()
    if args.live and args.output_dir is None:
        parser.error("Live execution requires a fresh private output directory")
    try:
        result = asyncio.run(
            execute(
                args.study_dir,
                args.output_dir,
                live=args.live,
                authorized_attempts=args.authorized_attempts,
                delay=args.delay_seconds,
            )
        )
    except Exception:
        parser.exit(
            1,
            "Pilot stopped; no automatic retry. Preserved evidence must be inspected before any new allowance.\n",
        )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
