"""Submit while the worker is stopped, then verify after starting the worker.

Usage: smoke_jobs.py submit | check. Uses only the local fake-provider API.
"""

import json
import sys
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "queue-smoke.json"
opener = build_opener(ProxyHandler({}))


def request(path, data=None, key=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    req = Request(
        "http://127.0.0.1:8000" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
    )
    with opener.open(req, timeout=10) as response:
        return json.load(response)


if sys.argv[1:] == ["submit"]:
    dataset = request(
        "/datasets",
        {
            "name": "queue-smoke",
            "version": "1",
            "cases": [
                {
                    "external_id": "capital",
                    "question": "Capital of France?",
                    "expected_answer": "Paris",
                    "context": "Paris",
                    "exact_match": True,
                }
            ],
        },
    )
    key = str(uuid4())
    payload = {"dataset_id": dataset["id"]}
    run = request("/queued-runs", payload, key)
    assert run["simulated"] and run["execution_mode"] == "queued"
    assert request("/queued-runs", payload, key)["id"] == run["id"]
    jobs = request("/runs/" + run["id"] + "/jobs")
    assert len(jobs) == 1
    ARTIFACT.parent.mkdir(exist_ok=True)
    ARTIFACT.write_text(json.dumps({"run_id": run["id"]}))
    print("PASS: queued submission is persisted and duplicate submission returns the same run")
elif sys.argv[1:] == ["check"]:
    run_id = json.loads(ARTIFACT.read_text())["run_id"]
    for _ in range(100):
        run = request("/runs/" + run_id)
        if run["status"] != "RUNNING":
            break
        time.sleep(0.1)
    assert run["status"] == "COMPLETED" and run["simulated"]
    assert len(run["results"]) == 1 and run["results"][0]["passed"]
    jobs = request("/runs/" + run_id + "/jobs")
    assert jobs[0]["status"] == "COMPLETED" and jobs[0]["attempts"] == 1
    print("PASS: separate worker completed the persisted job with one accepted result")
else:
    raise SystemExit("Usage: smoke_jobs.py submit | check")
