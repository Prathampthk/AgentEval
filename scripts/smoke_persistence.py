"""Create a persisted fake evaluation, then check it again after an API restart.

Run with `create` first; after restarting the server, run with `check`.
Only identifiers are written to artifacts/persistence-smoke.json.
"""

import json
import sys
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "persistence-smoke.json"
opener = build_opener(ProxyHandler({}))


def request(path, data=None):
    req = Request(
        "http://127.0.0.1:8000" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with opener.open(req, timeout=15) as response:
        return json.load(response)


if sys.argv[1:] == ["create"]:
    assert request("/health/ready")["database"] == "ready"
    dataset = request(
        "/datasets",
        {
            "name": "local-smoke",
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
    run = request("/runs", {"dataset_id": dataset["id"]})
    assert run["status"] == "COMPLETED" and run["simulated"]
    assert len(run["results"]) == 1 and run["results"][0]["passed"]
    ARTIFACT.parent.mkdir(exist_ok=True)
    ARTIFACT.write_text(json.dumps({"dataset_id": dataset["id"], "run_id": run["id"]}))
    print("PASS: dataset and completed evaluation were persisted")
elif sys.argv[1:] == ["check"]:
    ids = json.loads(ARTIFACT.read_text())
    run = request("/runs/" + ids["run_id"])
    dataset = request("/datasets/" + ids["dataset_id"])
    assert run["dataset_id"] == dataset["id"]
    assert run["status"] == "COMPLETED" and run["results"][0]["answer"] == "Paris"
    assert run["simulated"] and run["results"][0]["passed"]
    print("PASS: persisted dataset and result remain readable")
else:
    raise SystemExit("Usage: smoke_persistence.py create | check")
