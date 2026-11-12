"""Validate genuine RAG reviews against frozen evidence; never fill human decisions."""

import argparse
import hashlib
import json
from pathlib import Path


def summarize(review_path, collection_path, fixture_path):
    raw = review_path.read_bytes()
    packet = json.loads(raw)
    collection = json.loads(collection_path.read_bytes())
    fixture_raw = fixture_path.read_bytes()
    fixture = json.loads(fixture_raw)
    digest = hashlib.sha256(fixture_raw).hexdigest()
    if packet["source_sha256"] != digest or collection["source_sha256"] != digest:
        raise ValueError("Fixture fingerprint mismatch")
    if collection["status"] != "COMPLETED" or packet["collection_status"] != "COMPLETED":
        raise ValueError("Review requires a completed collection")

    def unique(rows, key):
        indexed = {r[key]: r for r in rows}
        if len(indexed) != len(rows):
            raise ValueError("Duplicate question IDs")
        return indexed

    questions = unique(fixture["questions"], "id")
    responses = unique(collection["responses"], "question_id")
    reviews = unique(packet["reviews"], "question_id")
    if questions.keys() != responses.keys() or questions.keys() != reviews.keys():
        raise ValueError("Missing or unknown question IDs")
    groups = {
        name: {
            "total": 0,
            "reviewed": 0,
            "answer_supported": 0,
            "citations_supported": 0,
            "appropriate_abstention": 0,
        }
        for name in ("answerable", "unanswerable")
    }
    pending = []
    allowed = {
        "question_id",
        "question",
        "answer",
        "supplied_evidence",
        "context_truncated",
        "ready_for_review",
        "answer_supported",
        "citations_supported",
        "appropriate_abstention",
        "reviewer",
        "notes",
    }
    for identifier, row in reviews.items():
        if set(row) != allowed:
            raise ValueError("Unexpected or missing review fields")
        response, question = responses[identifier], questions[identifier]
        if (
            row["question"] != question["question"]
            or row["question"] != response["question"]
            or row["answer"] != response["answer"]
            or row["supplied_evidence"] != response["supplied_context"]
            or type(row["context_truncated"]) is not bool
            or row["context_truncated"] != response["context_truncated"]
            or row["ready_for_review"] is not True
            or row["answer"] is None
        ):
            raise ValueError("Review answer or supplied evidence differs from frozen collection")
        for key in ("answer_supported", "citations_supported", "appropriate_abstention"):
            if row[key] is not None and type(row[key]) is not bool:
                raise ValueError("Human decisions must be true, false or null")
        for key in ("reviewer", "notes"):
            if row[key] is not None and (not isinstance(row[key], str) or not row[key].strip()):
                raise ValueError("Reviewer and notes must be nonempty text or null")
        answerable = question["expected_answer"] is not None
        if answerable and row["appropriate_abstention"] is not None:
            raise ValueError("Abstention assessment is reserved for unanswerable questions")
        completed = (
            row["answer_supported"] is not None
            and row["citations_supported"] is not None
            and row["reviewer"] is not None
            and (answerable or row["appropriate_abstention"] is not None)
        )
        group = groups["answerable" if answerable else "unanswerable"]
        group["total"] += 1
        if not completed:
            pending.append(identifier)
            continue
        group["reviewed"] += 1
        for key in ("answer_supported", "citations_supported", "appropriate_abstention"):
            group[key] += int(row[key] is True)
    for name, group in groups.items():
        for key in ("answer_supported", "citations_supported", "appropriate_abstention"):
            applicable = key != "appropriate_abstention" or name == "unanswerable"
            group[key + "_rate"] = (
                group[key] / group["reviewed"] if group["reviewed"] and applicable else None
            )
    return {
        "status": "HUMAN_REVIEW_PENDING" if pending else "HUMAN_REVIEW_COMPLETE",
        "fixture_sha256": digest,
        "review_file_sha256": hashlib.sha256(raw).hexdigest(),
        "collection_sha256": hashlib.sha256(collection_path.read_bytes()).hexdigest(),
        "question_count": len(questions),
        "reviewed_count": len(questions) - len(pending),
        "pending_question_ids": pending,
        "groups": groups,
        "scope": "User-supplied decisions only; no labels generated. Rates use fully reviewed rows in each group; absent reviews yield null rates. Reviewer identifiers and notes are excluded.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--collection", type=Path, default=Path("reports/live-rag-study-v1.json"))
    parser.add_argument("--fixture", type=Path, default=Path("examples/rag_study.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = summarize(args.reviews, args.collection, args.fixture)
        with args.output.open("x") as file:
            file.write(json.dumps(result, indent=2) + "\n")
    except (OSError, ValueError, KeyError, TypeError):
        parser.error(
            "Review validation failed or output exists; preserve original evidence and choose a new output path"
        )
    print(
        f"{result['status']}: {result['reviewed_count']}/{result['question_count']} fully reviewed. No human decisions generated."
    )


if __name__ == "__main__":
    main()
