"""Sequential durable worker. Bounded parallel execution is a later milestone."""

import asyncio
import json
import logging
import os
import random
import signal
from uuid import uuid4

from agenteval.database import Database
from agenteval.jobs import JobQueue, LostLease
from agenteval.providers import ProviderError
from agenteval.runtime import provider_context
from agenteval.service import evaluate

logger = logging.getLogger("agenteval.worker")


def event(name, claim=None, **fields):
    payload = {"event": name, **fields}
    if claim:
        payload.update(
            job_id=str(claim.id),
            run_id=str(claim.run_id),
            attempt=claim.attempt,
            worker_id=claim.owner,
        )
    logger.info(json.dumps(payload))


async def run_once(queue, provider, owner, *, lease_seconds=60, heartbeat_seconds=15):
    if not 0 < heartbeat_seconds < lease_seconds:
        raise ValueError("Heartbeat must be positive and shorter than the lease")
    claim = await queue.claim(owner, provider, lease_seconds)
    if claim is None:
        return False
    event("job_claimed", claim)
    lost = asyncio.Event()

    async def heartbeat():
        while True:
            await asyncio.sleep(heartbeat_seconds)
            try:
                if await queue.renew(claim, lease_seconds):
                    continue
            except Exception:
                event("heartbeat_failed", claim)
            lost.set()
            return

    async def execute():
        async with asyncio.timeout(claim.job_timeout):
            return await evaluate(claim.request, provider, claim.provider_timeout)

    heart = asyncio.create_task(heartbeat())
    evaluation = asyncio.create_task(execute())
    lease_lost = asyncio.create_task(lost.wait())
    try:
        done, _ = await asyncio.wait((evaluation, lease_lost), return_when=asyncio.FIRST_COMPLETED)
        if lease_lost in done:
            event("lease_lost", claim)
            return True
        try:
            result = await evaluation
        except (ProviderError, TimeoutError) as exc:
            category = exc.category if isinstance(exc, ProviderError) else "job_timeout"
            retryable = exc.retryable if isinstance(exc, ProviderError) else True
            delay = random.uniform(0, min(60, 2 ** (claim.attempt - 1)))
            await queue.fail(claim, category, retryable=retryable, delay_seconds=delay)
            event("job_attempt_failed", claim, category=category, retry_delay_seconds=delay)
        except Exception:
            await queue.fail(claim, "execution_error", retryable=False)
            event("job_attempt_failed", claim, category="execution_error")
        else:
            await queue.complete(claim, result)
            event("job_completed", claim)
    except LostLease:
        event("lease_lost", claim)
    finally:
        for task in (heart, evaluation, lease_lost):
            task.cancel()
        await asyncio.gather(heart, evaluation, lease_lost, return_exceptions=True)
    return True


async def serve(stop, queue, provider, owner):
    while not stop.is_set():
        try:
            recovered = await queue.recover()
            if recovered:
                event("leases_recovered", count=recovered)
            active = asyncio.create_task(run_once(queue, provider, owner))
            stopped = asyncio.create_task(stop.wait())
            try:
                done, _ = await asyncio.wait((active, stopped), return_when=asyncio.FIRST_COMPLETED)
                if stopped in done:
                    # Let an in-progress attempt drain, then leave its lease for recovery.
                    try:
                        await asyncio.wait_for(active, timeout=50)
                    except TimeoutError:
                        event("shutdown_drain_timeout", worker_id=owner)
                    break
                if await active:
                    continue
            finally:
                active.cancel()
                stopped.cancel()
                await asyncio.gather(active, stopped, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A database interruption leaves the current lease to expire. Never
            # log raw DB exceptions, parameters, provider content or credentials.
            event("worker_iteration_failed", worker_id=owner)
        try:
            await asyncio.wait_for(stop.wait(), timeout=1)
        except TimeoutError:
            pass


async def main():
    url = os.getenv("AGENTEVAL_DATABASE_URL")
    if not url:
        raise RuntimeError("AGENTEVAL_DATABASE_URL is required")
    database = Database(url)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await database.check_ready()
        async with provider_context() as provider:
            await serve(stop, JobQueue(database), provider, f"worker-{uuid4()}")
    finally:
        await database.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
