from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agenteval.api import create_app
from agenteval.persistence_schemas import DatasetCreate
from agenteval.providers import FakeProvider

CASE = {"external_id": "a", "question": "q", "expected_answer": "a"}


@pytest.mark.parametrize(
    "cases",
    [
        [],
        [CASE, CASE],
        [{**CASE, "question": " "}],
        [{**CASE, "external_id": str(i)} for i in range(21)],
    ],
)
def test_invalid_dataset_rejected(cases):
    with pytest.raises(ValidationError):
        DatasetCreate(name="demo", version="1", cases=cases)


def test_persistence_routes_require_configuration():
    with TestClient(create_app(FakeProvider())) as client:
        response = client.post("/datasets", json={"name": "demo", "version": "1", "cases": [CASE]})
        assert response.status_code == 503
        assert client.get(f"/runs/{uuid4()}").status_code == 503
        assert client.get("/health/ready").json()["database"] == "disabled"
