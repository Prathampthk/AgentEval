import runpy
from pathlib import Path

import pytest

from agenteval.providers import ProviderError


async def test_operation_budget_counts_failures_and_never_retries(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    budget_type = runpy.run_path(str(root / "scripts/collect_rag_study.py"))["Budget"]
    report = {"attempted_operations": 0, "operation_types": []}
    checkpoints, calls = [], []
    budget = budget_type(1, 0, report, lambda: checkpoints.append(report["attempted_operations"]))

    async def failed():
        calls.append("called")
        raise ProviderError("unavailable", retryable=True)

    with pytest.raises(ProviderError, match="unavailable"):
        await budget.call("generation", failed)
    with pytest.raises(ProviderError, match="study_budget_exhausted"):
        await budget.call("generation", failed)
    assert calls == ["called"] and checkpoints == [1]
    assert report == {"attempted_operations": 1, "operation_types": ["generation"]}


def test_review_packet_excludes_judge_opinions_and_preserves_existing_work(tmp_path):
    import json

    prepare = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/prepare_rag_answers.py")
    )["prepare_review"]
    source, output = tmp_path / "collection.json", tmp_path / "review.json"
    source.write_text(
        json.dumps(
            {
                "source_sha256": "fixture-hash",
                "status": "COMPLETED",
                "responses": [
                    {
                        "question_id": "q1",
                        "question": "Question",
                        "answer": "Actual answer",
                        "supplied_context": "Exact evidence",
                        "context_truncated": False,
                        "judgment": {"correctness": 2},
                        "expected_answer": "Hidden reference",
                    }
                ],
            }
        )
    )
    packet = prepare(source, output)
    row = packet["reviews"][0]
    assert row["answer"] == "Actual answer" and row["supplied_evidence"] == "Exact evidence"
    assert row["ready_for_review"] is True
    assert all(
        row[key] is None
        for key in [
            "answer_supported",
            "citations_supported",
            "appropriate_abstention",
            "reviewer",
            "notes",
        ]
    )
    assert "judgment" not in row and "expected_answer" not in row
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        prepare(source, output)
    assert output.read_bytes() == before
