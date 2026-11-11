"""Collect bounded judge predictions, preserving successes without creating human labels."""

import argparse
import asyncio
import hashlib
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agenteval.domain import JudgeInput
from agenteval.providers import ProviderError
from agenteval.runtime import provider_context


def select_examples(examples, limit, seed):
    selected = list(examples)
    random.Random(seed).shuffle(selected)
    return selected[:limit]


def save(path, value):
    temporary = path.with_name(path.name + "." + str(uuid4()) + ".tmp")
    try:
        with open(temporary, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as file:
            file.write(json.dumps(value, indent=2) + "\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def collect(provider, examples, output, *, seed=42, delay_seconds=0):
    if not 1 <= len(examples) <= (50 if provider.simulated else 10):
        raise ValueError("Sample exceeds the bounded judge request limit")
    metadata_path = output.with_suffix(".meta.json")
    if output == metadata_path or output.exists() or metadata_path.exists():
        raise FileExistsError(
            "Choose new output and metadata paths; existing evidence is preserved"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservations happen before any requests, including racing collectors.
    for path in (output, metadata_path):
        with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)):
            pass
    rows = []
    metadata = {
        "status": "IN_PROGRESS",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": provider.name,
        "model": provider.model,
        "simulated": provider.simulated,
        "judge_prompt_version": getattr(provider, "judge_prompt_version", "v1"),
        "judge_prompt_sha256": getattr(provider, "judge_prompt_sha256", None),
        "seed": seed,
        "selected_ids": [e["example_id"] for e in examples],
        "selected_examples_sha256": hashlib.sha256(
            json.dumps(examples, sort_keys=True).encode()
        ).hexdigest(),
        "request_limit": len(examples),
        "requests_started": 0,
        "responses_saved": 0,
        "delay_seconds": delay_seconds,
        "automatic_retries": False,
        "billing_tier_verified": False,
        "usage_scope": "Successful saved responses only; failed/uncertain calls may incur usage.",
    }
    save(output, rows)
    save(metadata_path, metadata)
    try:
        for index, example in enumerate(examples):
            if index and delay_seconds:
                await asyncio.sleep(delay_seconds)
            metadata["requests_started"] += 1
            save(metadata_path, metadata)
            async with asyncio.timeout(30):
                response = await provider.judge(
                    JudgeInput(
                        question=example["question"],
                        expected_answer=example["expected_answer"],
                        context=example["context"],
                        answer=example["response"],
                    )
                )
            judgment = response.judgment
            rows.append(
                {
                    "example_id": example["example_id"],
                    "rubric_version": "v1",
                    "provider": provider.name,
                    "model": provider.model,
                    "simulated": provider.simulated,
                    "judge_prompt_version": getattr(provider, "judge_prompt_version", "v1"),
                    "judge_prompt_sha256": getattr(provider, "judge_prompt_sha256", None),
                    "passed": judgment.correctness == 2
                    and judgment.relevance == 2
                    and judgment.groundedness == 2,
                    "judgment": judgment.model_dump(),
                    "usage": response.usage.model_dump(),
                }
            )
            save(output, rows)
            metadata["responses_saved"] = len(rows)
            save(metadata_path, metadata)
    except BaseException as exc:
        metadata["status"] = "STOPPED"
        # Never persist provider exception text: it can contain credentials or request content.
        metadata["error_category"] = (
            exc.category if isinstance(exc, ProviderError) else "interrupted_or_failed"
        )
        raise
    else:
        metadata["status"] = "COMPLETED"
    finally:
        metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        save(metadata_path, metadata)
    return rows


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--plan", action="store_true", help="Write selection only; no provider calls"
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0, help="Skip this many shuffled examples")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--judge-prompt", choices=("v1", "candidate-v2"), default="v1")
    parser.add_argument("--delay-seconds", type=float)
    parser.add_argument("--output", type=Path, default=Path("artifacts/judge_predictions.json"))
    args = parser.parse_args()
    live = os.getenv("AGENTEVAL_PROVIDER", "fake") != "fake"
    maximum = 10 if live else 50
    if args.offset < 0 or not 1 <= args.limit <= maximum:
        parser.error(f"offset must be nonnegative and limit must be 1–{maximum}")
    delay_seconds = args.delay_seconds if args.delay_seconds is not None else (6 if live else 0)
    if not 0 <= delay_seconds <= 60:
        parser.error("delay-seconds must be finite and between 0 and 60")
    if live and not args.live and not args.plan:
        parser.error("Live requests require --live and confirmed usage/budget authorization")
    if args.judge_prompt != "v1" and not live and not args.plan:
        parser.error("The candidate judge prompt requires the Gemini provider")
    if args.output.exists() or args.output.with_suffix(".meta.json").exists():
        parser.error("Output exists; choose a new path to preserve evidence")
    source = json.loads(Path("examples/judge_study.json").read_text())
    if args.offset + args.limit > len(source):
        parser.error("Selected range exceeds the available examples")
    examples = select_examples(
        source,
        args.offset + args.limit,
        args.seed,
    )[args.offset :]
    if args.plan:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as file:
            json.dump(
                {
                    "status": "PLAN_ONLY",
                    "seed": args.seed,
                    "offset": args.offset,
                    "judge_prompt_version": args.judge_prompt,
                    "selected_ids": [e["example_id"] for e in examples],
                    "provider_calls": 0,
                    "human_labels_generated": 0,
                },
                file,
                indent=2,
            )
            file.write("\n")
        print(f"Saved offline selection: {args.output}; no provider calls")
        return
    try:
        async with provider_context(judge_prompt_version=args.judge_prompt) as provider:
            rows = await collect(
                provider, examples, args.output, seed=args.seed, delay_seconds=delay_seconds
            )
    except Exception:
        raise SystemExit(
            "Judge collection stopped; no automatic retry. Any saved predictions/metadata are preserved."
        ) from None
    print(f"Saved {len(rows)} judge responses; no human labels were created")


if __name__ == "__main__":
    asyncio.run(main())
