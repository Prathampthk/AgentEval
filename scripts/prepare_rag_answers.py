"""Create a separate human-review packet from saved answers, excluding AI judge scores."""

import argparse
import json
import os
from pathlib import Path


def prepare_review(source, output):
    collection = json.loads(source.read_text())
    rows = collection["responses"]
    ids = [row["question_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate collected question IDs")
    packet = {
        "source_sha256": collection["source_sha256"],
        "collection_status": collection["status"],
        "instructions": "Review each actual answer against supplied_evidence. Supply your own judgments and reviewer identifier; null means unreviewed. Judge opinions and reference answers are excluded.",
        "reviews": [
            {
                "question_id": row["question_id"],
                "question": row["question"],
                "answer": row["answer"],
                "supplied_evidence": row["supplied_context"],
                "context_truncated": row["context_truncated"],
                "ready_for_review": row["answer"] is not None,
                "answer_supported": None,
                "citations_supported": None,
                "appropriate_abstention": None,
                "reviewer": None,
                "notes": None,
            }
            for row in rows
        ],
    }
    with open(output, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as file:
        file.write(json.dumps(packet, indent=2) + "\n")
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        packet = prepare_review(args.collection, args.output)
    except (OSError, ValueError, KeyError, TypeError):
        parser.error(
            "Use valid saved collection evidence and a new output file; existing human work is preserved"
        )
    print(f"Prepared {len(packet['reviews'])} review entries; zero human decisions generated.")


if __name__ == "__main__":
    main()
