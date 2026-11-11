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
