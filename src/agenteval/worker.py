"""Fixed-size durable worker pool with cooperative drain and lease recovery."""

import asyncio
import json
import logging
import math
import os
import random
import signal
from dataclasses import dataclass
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


@dataclass
class WorkerMetrics:
    active_evaluations: int = 0
    max_active_evaluations: int = 0
    attempts_started: int = 0

    def entered(self):
        self.active_evaluations += 1
        self.attempts_started += 1
        self.max_active_evaluations = max(self.max_active_evaluations, self.active_evaluations)

    def exited(self):
        self.active_evaluations -= 1


def validate_pool(concurrency, poll_seconds, shutdown_seconds, lease_seconds, heartbeat_seconds):
    if type(concurrency) is not int or not 1 <= concurrency <= 16:
        raise ValueError("Worker concurrency must be an integer between 1 and 16")
    if not all(
        math.isfinite(value) and value > 0
        for value in (poll_seconds, shutdown_seconds, lease_seconds, heartbeat_seconds)
    ):
        raise ValueError("Worker timing values must be positive and finite")
    if not heartbeat_seconds < lease_seconds <= 3600:
        raise ValueError("Heartbeat must be shorter than a lease of at most 3600 seconds")


async def run_once(
    queue, provider, owner, *, lease_seconds=60, heartbeat_seconds=15, stop=None, metrics=None
):
    if not 0 < heartbeat_seconds < lease_seconds:
        raise ValueError("Heartbeat must be positive and shorter than the lease")
    claim = await queue.claim(owner, provider, lease_seconds)
    if claim is None:
        return False
    if stop is not None and stop.is_set():
        # A claim already in flight when shutdown began can commit. Do not begin
        # provider work; leave the persisted lease for normal recovery.
        event("claim_abandoned_on_shutdown", claim)
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
        if metrics is not None:
            metrics.entered()
        try:
            async with asyncio.timeout(claim.job_timeout):
                return await evaluate(claim.request, provider, claim.provider_timeout)
        finally:
            if metrics is not None:
                metrics.exited()

    prefix = f"agenteval:{owner}:{claim.id}"
    heart = asyncio.create_task(heartbeat(), name=f"{prefix}:heartbeat")
    evaluation = asyncio.create_task(execute(), name=f"{prefix}:evaluation")
    lease_lost = asyncio.create_task(lost.wait(), name=f"{prefix}:lease-watch")
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


async def serve(
    stop,
    queue,
    provider,
    owner,
    *,
    concurrency=1,
    poll_seconds=1,
    shutdown_seconds=50,
    lease_seconds=60,
    heartbeat_seconds=15,
    metrics=None,
):
    validate_pool(concurrency, poll_seconds, shutdown_seconds, lease_seconds, heartbeat_seconds)
    metrics = metrics if metrics is not None else WorkerMetrics()

    async def idle():
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
        except TimeoutError:
            pass

    async def lane(index):
        lane_owner = f"{owner}:{index}"
        while not stop.is_set():
            try:
                if await run_once(
                    queue,
                    provider,
                    lane_owner,
                    lease_seconds=lease_seconds,
                    heartbeat_seconds=heartbeat_seconds,
                    stop=stop,
                    metrics=metrics,
                ):
                    continue
            except asyncio.CancelledError:
                raise
            except Exception:
                # Leave uncertain work leased for recovery. Other lanes continue.
                event("worker_iteration_failed", worker_id=lane_owner)
            await idle()

    async def recovery():
        while not stop.is_set():
            try:
                count = await queue.recover()
                if count:
                    event("leases_recovered", count=count)
            except asyncio.CancelledError:
                raise
            except Exception:
                event("recovery_iteration_failed", worker_id=owner)
            await idle()

    event(
        "worker_pool_started", worker_id=owner, concurrency=concurrency, concurrency_scope="process"
    )
    tasks = [
        asyncio.create_task(lane(i), name=f"agenteval:{owner}:lane:{i}") for i in range(concurrency)
    ]
    tasks.append(asyncio.create_task(recovery(), name=f"agenteval:{owner}:recovery"))
    try:
        await stop.wait()
        # One shared drain deadline for the entire pool, not one per lane.
        _, pending = await asyncio.wait(tasks, timeout=shutdown_seconds)
        if pending:
            event("shutdown_drain_timeout", worker_id=owner, pending_loops=len(pending))
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        event(
            "worker_pool_stopped",
            worker_id=owner,
            max_active_evaluations=metrics.max_active_evaluations,
            active_evaluations=metrics.active_evaluations,
            attempts_started=metrics.attempts_started,
        )
    return metrics


async def main():
    url = os.getenv("AGENTEVAL_DATABASE_URL")
    if not url:
        raise RuntimeError("AGENTEVAL_DATABASE_URL is required")
    try:
        concurrency = int(os.getenv("AGENTEVAL_WORKER_CONCURRENCY", "1"))
        validate_pool(concurrency, 1, 50, 60, 15)
    except ValueError:
        raise RuntimeError(
            "AGENTEVAL_WORKER_CONCURRENCY must be an integer between 1 and 16"
        ) from None
    database = Database(url)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await database.check_ready()
        async with provider_context() as provider:
            await serve(
                stop, JobQueue(database), provider, f"worker-{uuid4()}", concurrency=concurrency
            )
    finally:
        await database.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
