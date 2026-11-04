"""Independent fake worker process controlled by test-file barriers; no live API."""

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy.engine import make_url

from agenteval.database import Database
from agenteval.jobs import JobQueue, LostLease
from agenteval.persistence_schemas import RunCreate
from agenteval.providers import FakeProvider
from agenteval.service import evaluate


async def gate(path):
    async with asyncio.timeout(15):
        while not path.exists():
            await asyncio.sleep(0.01)


def write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True)
    parser.add_argument("--control", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset")
    parser.add_argument("--key", default="process-submission")
    args = parser.parse_args()
    url = os.environ["AGENTEVAL_TEST_DATABASE_URL"]
    assert make_url(url).database.endswith("_test")
    database = Database(url)
    queue = JobQueue(database)
    provider = FakeProvider()
    provider.model = args.model
    control = Path(args.control)
    output = control / f"result-{args.index}.json"
    try:
        write(control / f"ready-{args.index}", {"pid": os.getpid()})
        await gate(control / "go")
        if args.action == "submit":
            run_id = await queue.submit(
                RunCreate(dataset_id=UUID(args.dataset)), provider, args.key
            )
            write(output, {"run_id": str(run_id), "pid": os.getpid()})
            return
        claim = await queue.claim(f"process-{args.index}", provider)
        if claim is None:
            write(output, {"claim": None, "pid": os.getpid()})
            return
        write(control / f"claimed-{args.index}", {"job_id": str(claim.id), "pid": os.getpid()})
        if args.action == "claim":
            write(output, {"claim": str(claim.id), "pid": os.getpid()})
            return
        if args.action == "crash-before":
            os._exit(86)
        if args.action == "hold":
            await gate(control / "finish")
        response = await evaluate(claim.request, provider)
        # This fsynced file is a controlled external side effect, independent of
        # the result transaction. A replacement cannot undo or deduplicate it.
        with (control / "external-effects.jsonl").open("a") as file:
            file.write(
                json.dumps({"job_id": str(claim.id), "attempt": claim.attempt, "pid": os.getpid()})
                + "\n"
            )
            file.flush()
            os.fsync(file.fileno())
        if args.action == "crash-response":
            os._exit(86)
        try:
            await queue.complete(claim, response)
            write(output, {"outcome": "COMPLETED", "pid": os.getpid()})
        except LostLease:
            write(output, {"outcome": "LOST_LEASE", "pid": os.getpid()})
        if args.action == "crash-ack":
            os._exit(86)
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
