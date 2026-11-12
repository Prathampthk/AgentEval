"""Explicitly synthetic review fixtures; these are not human-study evidence."""

import hashlib
import json
import runpy
from pathlib import Path

import pytest

summarize = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/summarize_rag_review.py")
)["summarize"]


@pytest.fixture
def files(tmp_path):
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "questions": [
                    {"id": "known", "question": "Known?", "expected_answer": "Reference"},
                    {"id": "unknown", "question": "Unknown?", "expected_answer": None},
                ]
            }
        )
    )
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    responses, reviews = [], []
    for identifier, question in [("known", "Known?"), ("unknown", "Unknown?")]:
        responses.append(
            {
                "question_id": identifier,
                "question": question,
                "answer": "Synthetic answer",
                "supplied_context": "Synthetic evidence",
                "context_truncated": False,
            }
        )
        reviews.append(
            {
                "question_id": identifier,
                "question": question,
                "answer": "Synthetic answer",
                "supplied_evidence": "Synthetic evidence",
                "context_truncated": False,
                "ready_for_review": True,
                "answer_supported": None,
                "citations_supported": None,
                "appropriate_abstention": None,
                "reviewer": None,
                "notes": None,
            }
        )
    collection, review = tmp_path / "collection.json", tmp_path / "reviews.json"
    collection.write_text(
        json.dumps({"source_sha256": digest, "status": "COMPLETED", "responses": responses})
    )
    review.write_text(
        json.dumps({"source_sha256": digest, "collection_status": "COMPLETED", "reviews": reviews})
    )
    return review, collection, fixture


def test_blank_reviews_remain_pending_with_null_rates(files):
    before = files[0].read_bytes()
    result = summarize(*files)
    assert result["status"] == "HUMAN_REVIEW_PENDING" and result["reviewed_count"] == 0
    assert all(g["answer_supported_rate"] is None for g in result["groups"].values())
    assert files[0].read_bytes() == before


def test_only_complete_attributed_rows_contribute_to_rates(files):
    packet = json.loads(files[0].read_text())
    packet["reviews"][0].update(
        answer_supported=True, citations_supported=False, reviewer="SYNTHETIC"
    )
    packet["reviews"][1].update(
        answer_supported=True, citations_supported=True, appropriate_abstention=True
    )
    files[0].write_text(json.dumps(packet))
    result = summarize(*files)
    assert result["reviewed_count"] == 1 and result["pending_question_ids"] == ["unknown"]
    assert result["groups"]["answerable"]["citations_supported_rate"] == 0
    assert result["groups"]["unanswerable"]["appropriate_abstention_rate"] is None
    packet["reviews"][1]["reviewer"] = "SYNTHETIC"
    files[0].write_text(json.dumps(packet))
    assert summarize(*files)["status"] == "HUMAN_REVIEW_COMPLETE"


@pytest.mark.parametrize(
    "change", ["text", "boolean", "duplicate", "missing", "fingerprint", "abstention"]
)
def test_rejects_changed_evidence_and_invalid_decisions(files, change):
    packet = json.loads(files[0].read_text())
    row = packet["reviews"][0]
    if change == "text":
        row["supplied_evidence"] = "Edited evidence"
    elif change == "boolean":
        row["answer_supported"] = 1
    elif change == "duplicate":
        packet["reviews"].append(row.copy())
    elif change == "missing":
        packet["reviews"].pop()
    elif change == "fingerprint":
        packet["source_sha256"] = "wrong"
    else:
        row["appropriate_abstention"] = True
    files[0].write_text(json.dumps(packet))
    with pytest.raises(ValueError):
        summarize(*files)
