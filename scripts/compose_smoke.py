"""Check a running Compose deployment without any external provider calls."""

import json
import os
import time
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

opener = build_opener(ProxyHandler({}))
base = os.getenv("AGENTEVAL_SMOKE_URL", "http://127.0.0.1:8011")


def request(path, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    with opener.open(
        Request(
            base + path, data=data, headers={"Content-Type": "application/json", **(headers or {})}
        ),
        timeout=5,
    ) as response:
        return json.load(response)


request("/health/ready")
with opener.open(base + "/dashboard/", timeout=5) as response:
    assert response.status == 200
name = str(uuid4())
dataset = request(
    "/datasets",
    {
        "name": "compose-" + name,
        "version": "1",
        "cases": [
            {
                "external_id": "one",
                "question": "Capital of France?",
                "expected_answer": "Paris",
                "context": "Paris",
            }
        ],
    },
)
body = {"dataset_id": dataset["id"]}
headers = {"Idempotency-Key": name}
run = request("/queued-runs", body, headers)
assert request("/queued-runs", body, headers)["id"] == run["id"]
for _ in range(100):
    state = request("/runs/" + run["id"])
    if state["status"] != "RUNNING":
        break
    time.sleep(0.1)
assert state["status"] == "COMPLETED", state["status"]
assert len(state["results"]) == 1
print("Compose readiness, dashboard, idempotent submission and worker completion passed")
