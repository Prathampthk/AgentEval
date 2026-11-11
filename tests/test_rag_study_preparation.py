import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
prepare = runpy.run_path(str(ROOT / "scripts/prepare_rag_study.py"))["prepare"]


def test_preparation_counts_operations_and_leaves_human_decisions_empty(tmp_path):
    output = tmp_path / "study"
    plan = prepare(ROOT / "examples/rag_study.json", output)
    assert (output / "fixture.json").read_bytes() == (ROOT / "examples/rag_study.json").read_bytes()
    assert plan["status"] == "PREPARED_OFFLINE"
    assert plan["provider_calls_made"] == plan["human_labels_created"] == 0
    assert plan["live_execution_authorized"] is False
    assert plan["answerable_questions"] == 6 and plan["unanswerable_questions"] == 2
    assert plan["planned_successful_path_operations"] == {
        "document_embeddings": 6,
        "query_embeddings": 8,
        "generations": 8,
        "judgments": 6,
        "total": 28,
    }
    review = json.loads((output / "human_review.json").read_text())
    assert review["source_sha256"] == plan["source_sha256"]
    assert {r["question_id"] for r in review["reviews"]} == set(plan["question_ids"])
    for row in review["reviews"]:
        assert all(
            value is None for key, value in row.items() if key not in {"question_id", "question"}
        )
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(FileExistsError):
        prepare(ROOT / "examples/rag_study.json", output)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


@pytest.mark.parametrize("invalid", ["unknown", "duplicate", "unsupported", "too-small-k"])
def test_invalid_ground_truth_is_rejected_before_writing(tmp_path, invalid):
    fixture = json.loads((ROOT / "examples/rag_study.json").read_text())
    question = fixture["questions"][0]
    if invalid == "unknown":
        question["expected_document_ids"] = ["missing"]
    elif invalid == "duplicate":
        fixture["questions"].append(question.copy())
    elif invalid == "unsupported":
        question["expected_document_ids"] = []
    else:
        question["k"] = 1
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(fixture))
    output = tmp_path / "study"
    with pytest.raises(ValueError):
        prepare(source, output)
    assert not output.exists()
