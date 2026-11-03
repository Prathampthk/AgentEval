import httpx
import pytest

from agenteval.api import create_app
from agenteval.persistence_schemas import DatasetCreate, RunCreate
from agenteval.persistent_runs import execute_run
from agenteval.providers import FakeProvider

pytestmark = pytest.mark.integration


async def test_stored_run_comparison_and_export(db, pg_url):
    dataset, _ = await db.create_dataset(
        DatasetCreate(
            name="comparison",
            version="1",
            cases=[
                dict(external_id="a", question="Capital?", expected_answer="Paris", context="Paris")
            ],
        )
    )
    baseline = await execute_run(RunCreate(dataset_id=dataset.id), db, FakeProvider(), 1)
    candidate = await execute_run(
        RunCreate(dataset_id=dataset.id, prompt="A new prompt"), db, FakeProvider(), 1
    )
    app = create_app(FakeProvider(), database_url=pg_url)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/comparisons",
                json=dict(baseline_run_id=str(baseline.id), candidate_run_id=str(candidate.id)),
            )
            assert response.status_code == 200 and response.json()["outcome"] == "PASS"
            exported = (await client.get(f"/runs/{baseline.id}/comparison-input")).json()
            assert exported["expected_cases"] == 1 and exported["results"][0]["passed"]
