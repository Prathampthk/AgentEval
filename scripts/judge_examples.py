"""Judge provided responses; no generation or fabricated human labels.

Default fake provider is free. Explicit --live is additionally required for Gemini.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from agenteval.domain import JudgeInput
from agenteval.runtime import provider_context


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", default="artifacts/judge_predictions.json")
    args = parser.parse_args()
    if not 1 <= args.limit <= 50:
        parser.error("limit must be 1–50")
    if os.getenv("AGENTEVAL_PROVIDER", "fake") != "fake" and not args.live:
        parser.error("Live provider calls require --live and an agreed budget")
    if os.getenv("AGENTEVAL_PROVIDER", "fake") != "fake" and args.limit > 10:
        parser.error("The currently authorized live sample is capped at 10 judge calls")
    examples = json.loads(Path("examples/judge_study.json").read_text())[: args.limit]
    rows = []
    async with provider_context() as provider:
        for example in examples:
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
                    "passed": judgment.correctness == 2
                    and judgment.relevance == 2
                    and judgment.groundedness == 2,
                    "judgment": judgment.model_dump(),
                }
            )
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"Saved {len(rows)} judge responses; no human labels were created")


if __name__ == "__main__":
    asyncio.run(main())
