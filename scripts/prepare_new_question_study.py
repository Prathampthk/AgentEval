"""Prepare a disjoint synthetic judge pilot; never call providers or create human decisions."""

import argparse
import hashlib
import json
import os
import random
from pathlib import Path


def normalize(value):
    return " ".join(value.casefold().split())


def prepare(source, previous, output):
    raw = source.read_bytes()
    rows = json.loads(raw)
    old = json.loads(previous.read_bytes())
    fields = ("example_id", "question", "expected_answer", "context", "response", "category")
    if not isinstance(rows, list) or not rows:
        raise ValueError("A nonempty example list is required")
    for row in rows:
        if set(row) != set(fields) or any(
            not isinstance(row[key], str) or not row[key].strip() for key in fields
        ):
            raise ValueError("Every example requires nonempty string fields")
    ids = [r["example_id"] for r in rows]
    old_ids = {r["example_id"] for r in old}
    old_questions = {normalize(r["question"]) for r in old}
    if len(set(ids)) != len(ids) or set(ids) & old_ids:
        raise ValueError("Example IDs must be unique and disjoint from the previous study")
    questions = {normalize(r["question"]) for r in rows}
    if questions & old_questions:
        raise ValueError("A question overlaps the previous study")
    # All variants of one question must share the same reference evidence.
    for question in questions:
        references = {
            (r["context"], r["expected_answer"])
            for r in rows
            if normalize(r["question"]) == question
        }
        if len(references) != 1:
            raise ValueError("Variants of one question have conflicting references")
    packet = [{k: r[k] for k in fields if k != "category"} for r in rows]
    random.Random(42).shuffle(packet)
    plan = {
        "status": "PREPARED_OFFLINE_NOT_MEASURED",
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "previous_fixture_sha256": hashlib.sha256(previous.read_bytes()).hexdigest(),
        "example_ids": [r["example_id"] for r in packet],
        "distinct_questions": len(questions),
        "exact_normalized_question_overlap": 0,
        "semantic_overlap_review": "Human review required; string disjointness is not semantic independence",
        "proposed_repetitions": 3,
        "proposed_judge_operations": 3 * len(rows),
        "live_execution_authorized": False,
        "provider_calls": 0,
        "human_decisions_generated": 0,
        "scope": "Agent-authored synthetic pilot, not representative application data",
    }
    labels = [
        {
            "example_id": r["example_id"],
            "human_pass": None,
            "labeler": None,
            "notes": None,
            "rubric_version": "v1",
        }
        for r in packet
    ]
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    values = {
        "plan.json": plan,
        "human_review_packet.json": {"rubric_version": "v1", "examples": packet},
        "human_labels.json": labels,
    }
    for name, value in values.items():
        with open(output / name, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as f:
            f.write(json.dumps(value, indent=2) + "\n")
    with open(output / "fixture.json", "xb", opener=lambda p, flags: os.open(p, flags, 0o600)) as f:
        f.write(raw)
    return plan


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "examples/judge_new_questions.json")
    parser.add_argument("--previous", type=Path, default=root / "examples/judge_study.json")
    parser.add_argument("--output-dir", type=Path, default=root / "artifacts/judge-new-questions")
    args = parser.parse_args()
    try:
        plan = prepare(args.source, args.previous, args.output_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(
            f"Preparation stopped ({type(exc).__name__}); use valid input and a fresh directory"
        )
    print(f"Prepared {len(plan['example_ids'])} responses; zero calls and zero human decisions")


if __name__ == "__main__":
    main()
