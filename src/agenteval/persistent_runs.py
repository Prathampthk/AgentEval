"""Request-scoped persisted runs; deliberately not a durable execution queue."""

import asyncio
import json
import logging

from agenteval.database import Database
from agenteval.domain import EvaluationRequest
from agenteval.persistence_schemas import RunCreate
from agenteval.providers import Provider, ProviderError
from agenteval.service import evaluate

logger = logging.getLogger("agenteval")


async def execute_run(
    data: RunCreate, database: Database, provider: Provider, timeout_seconds: float
):
    dataset = await database.get_dataset(data.dataset_id)
    run_id = await database.start_run(
        dataset.id,
        provider,
        {
            "prompt": data.prompt,
            "provider_timeout_seconds": timeout_seconds,
            "temperature": 0 if not provider.simulated else None,
            "generation_max_output_tokens": 1024 if not provider.simulated else None,
            "judge_max_output_tokens": 2048 if not provider.simulated else None,
        },
    )
    logger.info(
        json.dumps({"event": "run_started", "run_id": str(run_id), "simulated": provider.simulated})
    )
    try:
        results = []
        for case in dataset.cases:
            results.append(
                await evaluate(
                    EvaluationRequest(
                        dataset_name=dataset.name,
                        dataset_version=dataset.version,
                        test_case_id=case.external_id,
                        question=case.question,
                        expected_answer=case.expected_answer,
                        context=case.context,
                        exact_match=case.exact_match,
                        prompt=data.prompt,
                    ),
                    provider,
                    timeout_seconds,
                )
            )
        await database.finish_run(run_id, results)
        logger.info(
            json.dumps({"event": "run_completed", "run_id": str(run_id), "results": len(results)})
        )
    except ProviderError as exc:
        await database.fail_run(run_id, exc.category)
        logger.warning(
            json.dumps({"event": "run_failed", "run_id": str(run_id), "category": exc.category})
        )
    except asyncio.CancelledError:
        # Best effort while the process/database are still alive, not crash recovery.
        await database.fail_run(run_id, "request_canceled")
        raise
    except Exception:
        await database.fail_run(run_id, "execution_error")
        raise
    return await database.get_run(run_id)
