import runpy
from pathlib import Path

import pytest

from agenteval.providers import FakeProvider

pytestmark = pytest.mark.integration


async def test_study_collects_isolated_fake_answers_without_human_labels(db, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    module = runpy.run_path(str(root / "scripts/collect_rag_study.py"))
    study = module["Study"].model_validate_json((root / "examples/rag_study.json").read_bytes())
    report = {"attempted_operations": 0, "operation_types": [], "documents": [], "responses": []}
    await module["collect"](db, FakeProvider(), study, report, lambda: None, limit=28, delay=0)
    assert report["status"] == "COMPLETED" and report["attempted_operations"] == 28
    assert len(report["documents"]) == 6 and len(report["responses"]) == 8
    assert all(r["answer"] for r in report["responses"])
    assert all(
        r["recall_at_k"] is None and r["hit_rate_at_k"] is None for r in report["responses"][-2:]
    )
    assert all("human_pass" not in r and "reviewer" not in r for r in report["responses"])
    with pytest.raises(ValueError, match="empty isolated"):
        await module["collect"](db, FakeProvider(), study, report, lambda: None, limit=28, delay=0)
