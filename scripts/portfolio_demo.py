"""Demonstrate queued persistence and comparison on a loopback fake-provider API."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Demo refuses HTTP redirects")


def demonstrate(request, *, wait_seconds=30):
    ready = request("/health/ready")
    if not (
        ready.get("provider") == "fake"
        and ready.get("simulated") is True
        and ready.get("database") == "ready"
    ):
        raise RuntimeError("Demo requires a ready database and explicitly simulated fake provider")

    dataset = request(
        "/datasets",
        {
            "name": "portfolio-demo",
            "version": "1",
            "cases": [
                {
                    "external_id": "capital",
                    "question": "Capital of France?",
                    "expected_answer": "Paris",
                    "context": "Paris",
                    "exact_match": True,
                },
                {
                    "external_id": "arithmetic",
                    "question": "What is two plus two?",
                    "expected_answer": "4",
                    "context": "4",
                    "exact_match": True,
                },
            ],
        },
    )
    runs = []
    for label in ("baseline", "candidate"):
        key = "portfolio-" + str(uuid4())
        body = {"dataset_id": dataset["id"]}
        run = request("/queued-runs", body, key)
        if request("/queued-runs", body, key)["id"] != run["id"]:
            raise RuntimeError("Submission replay returned a different run")
        deadline = time.monotonic() + wait_seconds
        while True:
            state = request("/runs/" + run["id"])
            if state["status"] != "RUNNING":
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Worker did not finish within the demonstration deadline")
            time.sleep(0.1)
        results = state["results"]
        jobs = request("/runs/" + run["id"] + "/jobs")
        if not (
            state["status"] == "COMPLETED"
            and state["execution_mode"] == "queued"
            and state["provider"] == "fake"
            and state["simulated"] is True
            and len(results) == len(jobs) == 2
            and all(r["passed"] and r["simulated"] for r in results)
            and all(j["status"] == "COMPLETED" and j["attempts"] == 1 for j in jobs)
        ):
            raise RuntimeError("Queued result or job checks failed")
        runs.append({"label": label, "run_id": run["id"], "accepted_results": len(results)})
    comparison = request(
        "/comparisons",
        {"baseline_run_id": runs[0]["run_id"], "candidate_run_id": runs[1]["run_id"]},
    )
    if comparison["outcome"] != "PASS":
        raise RuntimeError("Equivalent simulated runs did not pass comparison")
    return {
        "status": "PASS",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "simulated": True,
        "live_provider_calls": 0,
        "dataset_id": dataset["id"],
        "runs": runs,
        "comparison": comparison,
        "checks": [
            "fake-provider preflight",
            "idempotent replay",
            "queued completion",
            "comparison",
        ],
        "limits": [
            "Four accepted simulated results; not accuracy or throughput evidence.",
            "Repeated demos retain their own runs; no data is deleted.",
            "Human labels, live RAG, crash recovery and public safeguards are separate evidence.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    output = args.output or Path("artifacts") / ("portfolio-demo-" + str(uuid4()) + ".json")
    if output.exists():
        parser.error("Output already exists; choose a new path to preserve evidence")
    base = f"http://127.0.0.1:{args.port}"
    opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(path, body=None, key=None):
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Idempotency-Key"] = key
        with opener.open(
            Request(
                base + path,
                data=None if body is None else json.dumps(body).encode(),
                headers=headers,
            ),
            timeout=5,
        ) as response:
            return json.load(response)

    report = demonstrate(request)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as file:
        file.write(json.dumps(report, indent=2) + "\n")
    print(f"PASS: four simulated results, idempotent replay and comparison; evidence: {output}")


if __name__ == "__main__":
    main()
