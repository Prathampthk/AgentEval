"""Offline SDK wire-contract checks using synthetic responses."""

import json
import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from agenteval.api import create_app


@pytest.mark.parametrize("invalid_judgment", [False, True])
def test_gemini_json_schema_contract(monkeypatch, invalid_judgment):
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "gemini")
    monkeypatch.setenv("AGENTEVAL_MODEL", "gemini-3.1-flash-lite")
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test-placeholder")
    monkeypatch.delenv("AGENTEVAL_DATABASE_URL", raising=False)
    requests = []

    def block_network(*args, **kwargs):
        raise AssertionError("Unexpected network access in offline test")

    monkeypatch.setattr(socket.socket, "connect", block_network)

    async def mock_send(self, request, *args, **kwargs):
        assert request.url.host == "generativelanguage.googleapis.com"
        body = json.loads(request.content)
        requests.append(body)
        config = body.get("generationConfig", {})

        if config.get("responseMimeType") == "application/json":
            assert "responseJsonSchema" in config
            assert "responseSchema" not in config
            schema = config["responseJsonSchema"]
            assert schema["additionalProperties"] is False

            judgment = {
                "correctness": 2,
                "relevance": 2,
                "groundedness": 2,
                "explanation": "Matches the supplied context.",
            }
            if invalid_judgment:
                judgment["unexpected"] = "must be rejected"
            text = json.dumps(judgment)
        else:
            text = "Paris"

        payload = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": text}],
                    },
                },
            ],
        }
        return httpx.Response(200, request=request, json=payload)

    monkeypatch.setattr(httpx.AsyncClient, "send", mock_send)

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        response = client.post(
            "/evaluations",
            json={
                "dataset_name": "offline-contract",
                "dataset_version": "1",
                "test_case_id": "capital",
                "question": "Capital of France?",
                "expected_answer": "Paris",
                "context": "Paris is the capital of France.",
            },
        )

    assert len(requests) == 2
    if invalid_judgment:
        assert response.status_code == 502
        assert response.json()["detail"]["category"] == "invalid_output"
    else:
        assert response.status_code == 200
        assert response.json()["passed"] is True
        assert response.json()["simulated"] is False
