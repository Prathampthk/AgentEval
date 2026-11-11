"""Exercise document ingestion and scored retrieval against a local AgentEval API."""

import argparse
import json
import math
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from uuid import uuid4


def run_smoke(request, report, *, live):
    ready = request("/health/ready")
    provider = "gemini" if live else "fake"
    if (
        ready.get("provider") != provider
        or ready.get("simulated") is not (not live)
        or ready.get("database") != "ready"
        or not ready.get("model")
        or not ready.get("embedding_model")
    ):
        raise RuntimeError(
            "API must report the selected provider, both models, and a ready database"
        )
    report.update(
        provider=provider,
        model=ready["model"],
        embedding_model=ready["embedding_model"],
        simulated=not live,
        planned_live_provider_operations=5 if live else 0,
        documents=[],
    )

    project = "signal" + uuid4().hex
    documents = [
        ("Field manual", f"The {project} expedition signals its arrival with silver lanterns."),
        ("Arrival log", f"For the {project} expedition, the arrival signal is silver lanterns."),
    ]
    for title, content in documents:
        report["stage"] = f"ingest {title}"
        document = request("/documents", {"title": f"{project} {title}", "content": content})
        report["documents"].append(document)
        if document["chunks"] != 1 or document["simulated"] is not (not live):
            raise RuntimeError(
                "Each smoke document must produce one chunk for the selected provider"
            )

    expected = [document["id"] for document in report["documents"]]
    report["stage"] = "scored retrieval"
    evaluation = request(
        "/rag/evaluate",
        {
            "question": f"What arrival signal does the {project} expedition use? Cite both records.",
            "expected_answer": "silver lanterns",
            "expected_document_ids": expected,
            "k": 2,
        },
    )
    report["evaluation"] = evaluation
    retrieved = evaluation["retrieved"]
    result = evaluation["result"]
    if (
        len(retrieved) != 2
        or {row["document_id"] for row in retrieved} != set(expected)
        or not all(math.isfinite(row["distance"]) for row in retrieved)
        or evaluation["recall_at_k"] != 1.0
        or evaluation["hit_rate_at_k"] != 1
        or set(evaluation["context_chunk_ids"]) != {row["chunk_id"] for row in retrieved}
        or evaluation["context_truncated"] is not False
        or result["provider"] != provider
        or result["model"] != ready["model"]
        or result["simulated"] is not (not live)
    ):
        raise RuntimeError("Retrieved evidence or evaluation metadata did not match the fixture")
    report["cited_expected_document_ids"] = [
        identifier for identifier in expected if identifier in result["answer"]
    ]
    report["stage"] = "complete"
    report["status"] = "PASS"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Allow up to five Gemini operations")
    parser.add_argument("--port", type=int, help="Loopback port (default 8011 or 8012 with --live)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    port = args.port if args.port is not None else (8012 if args.live else 8011)
    if not 1 <= port <= 65535:
        parser.error("Port must be between 1 and 65535")
    output = args.output or Path("artifacts") / f"rag-smoke-{uuid4()}.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    def request(path, body=None):
        connection = HTTPConnection("127.0.0.1", port, timeout=95)
        try:
            connection.request(
                "GET" if body is None else "POST",
                path,
                body=None if body is None else json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            if response.status != (201 if path == "/documents" else 200):
                raise RuntimeError(f"{path} returned HTTP {response.status}")
            return json.load(response)
        finally:
            connection.close()

    report = {
        "status": "STOPPED",
        "stage": "readiness",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        file = output.open("x")
    except FileExistsError:
        parser.error("Output already exists. Choose a new path to preserve evidence.")
    with file:
        try:
            run_smoke(request, report, live=args.live)
        except (OSError, HTTPException, RuntimeError, ValueError, KeyError, TypeError) as exc:
            report["error"] = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
            raise SystemExit(
                f"RAG smoke stopped at {report['stage']}. Evidence: {output}"
            ) from None
        finally:
            file.write(json.dumps(report, indent=2) + "\n")
    print(f"PASS: scored RAG retrieved both fixture documents. Evidence: {output}")


if __name__ == "__main__":
    main()
