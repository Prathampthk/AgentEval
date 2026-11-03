"""Functional request against a running local fake-provider API."""

import json
from urllib.request import ProxyHandler, Request, build_opener

opener = build_opener(ProxyHandler({}))  # Loopback does not use the external egress proxy.
request = Request(
    "http://127.0.0.1:8000/evaluations",
    data=json.dumps(
        {
            "dataset_name": "demo",
            "dataset_version": "1",
            "test_case_id": "capital",
            "question": "Capital of France?",
            "expected_answer": "Paris",
            "context": "Paris",
            "exact_match": True,
        }
    ).encode(),
    headers={"Content-Type": "application/json"},
)
with opener.open(request, timeout=10) as response:
    result = json.load(response)
assert result["simulated"] is True
assert result["passed"] is True
assert result["answer"] == "Paris"
print("PASS: local HTTP evaluation returned the expected simulated result")
