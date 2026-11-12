import asyncio
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from agenteval.api import create_app
from agenteval.domain import GenerationInput
from agenteval.providers import FakeProvider, ProviderError
from agenteval.runtime import provider_context
from agenteval.server_budget import BudgetProvider, ServerBudget, configure


def test_failures_spend_attempts_and_restart_never_resets_ledger(tmp_path):
    path = tmp_path / "budget.sqlite3"
    budget = configure(path, 2, 100, 1)
    first = budget.reserve("judge")
    budget.finish(first, None, False)
    restarted = ServerBudget(path)
    second = restarted.reserve("embed")
    restarted.finish(second, None, False)
    with pytest.raises(ProviderError, match="provider_budget_exhausted"):
        budget.reserve("generate")
    assert restarted.status()["attempts_reserved"] == 2
    configure(path, 3, 100, 1)
    assert budget.status()["attempts_remaining"] == 1
    with pytest.raises(ProviderError):
        configure(path, 1, 100, 1)


def test_capacity_and_rolling_rate_rejections_do_not_dispatch_or_spend(tmp_path):
    budget = configure(tmp_path / "budget.sqlite3", 10, 1, 1)
    ticket = budget.reserve("generate")
    with pytest.raises(ProviderError, match="provider_capacity"):
        budget.reserve("judge")
    budget.finish(ticket, None, True)
    with pytest.raises(ProviderError, match="provider_rate_limited") as error:
        budget.reserve("judge")
    assert 1 <= error.value.retry_after_seconds <= 60
    assert budget.status()["attempts_reserved"] == 1


def test_independent_processes_share_the_same_total_ceiling(tmp_path):
    path = tmp_path / "budget.sqlite3"
    budget = configure(path, 6, 1000, 4)
    code = """
import sys,time
from agenteval.server_budget import ServerBudget
from agenteval.providers import ProviderError
b=ServerBudget(sys.argv[1])
for _ in range(100):
 try:
  ticket=b.reserve('generate');b.finish(ticket,None,True);print('admitted');break
 except ProviderError as e:
  if e.category=='provider_capacity':time.sleep(.01);continue
  print(e.category);break
"""

    def child(_):
        return subprocess.run(
            [sys.executable, "-c", code, str(path)], capture_output=True, check=True, text=True
        ).stdout.strip()

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(child, range(12)))
    assert results.count("admitted") == 6
    assert results.count("provider_budget_exhausted") == 6
    assert budget.status()["attempts_reserved"] == 6


def test_process_loss_keeps_uncertain_slot_closed_without_refund(tmp_path):
    path = tmp_path / "budget.sqlite3"
    budget = configure(path, 10, 100, 1)
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import os,sys; from agenteval.server_budget import ServerBudget; ServerBudget(sys.argv[1]).reserve('judge'); os._exit(0)",
            str(path),
        ],
        check=True,
    )
    assert budget.status()["active_or_uncertain"] == 1
    with pytest.raises(ProviderError, match="provider_capacity"):
        budget.reserve("judge")
    with pytest.raises(ProviderError):
        configure(path, 20, 100, 1)
    assert budget.status()["attempts_reserved"] == 1


async def test_wrapper_counts_failed_calls_and_preserves_prompt_metadata(tmp_path):
    budget = configure(tmp_path / "budget.sqlite3", 1, 100, 1)
    provider = FakeProvider()
    provider.judge_prompt_version = "synthetic-v2"
    provider.generate = AsyncMock(side_effect=ProviderError("invalid_request"))
    wrapped = BudgetProvider(provider, budget)
    data = GenerationInput(question="synthetic", context="fixture", prompt="fixture")
    with pytest.raises(ProviderError, match="invalid_request"):
        await wrapped.generate(data)
    with pytest.raises(ProviderError, match="provider_budget_exhausted"):
        await wrapped.generate(data)
    assert wrapped.judge_prompt_version == "synthetic-v2"
    provider.generate.assert_awaited_once()
    assert budget.status()["active_or_uncertain"] == 0


async def test_cancellation_retains_uncertain_slot_and_spent_attempt(tmp_path):
    budget = configure(tmp_path / "budget.sqlite3", 10, 100, 1)
    provider = FakeProvider()
    started = asyncio.Event()

    async def waiting(data):
        started.set()
        await asyncio.Event().wait()

    provider.generate = waiting
    task = asyncio.create_task(BudgetProvider(provider, budget).generate(None))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert budget.status()["active_or_uncertain"] == 1
    assert budget.status()["attempts_reserved"] == 1


@pytest.mark.parametrize("category", ["timeout", "network", "unavailable"])
async def test_ambiguous_provider_failure_keeps_admission_closed(tmp_path, category):
    budget = configure(tmp_path / "budget.sqlite3", 10, 100, 1)
    provider = FakeProvider()
    provider.generate = AsyncMock(side_effect=ProviderError(category, True))
    wrapped = BudgetProvider(provider, budget)
    with pytest.raises(ProviderError, match=category):
        await wrapped.generate(None)
    with pytest.raises(ProviderError, match="provider_capacity"):
        await wrapped.generate(None)
    provider.generate.assert_awaited_once()


def test_http_budget_exhaustion_and_retry_after_are_actionable(tmp_path):
    budget = configure(tmp_path / "budget.sqlite3", 10, 1, 1)
    provider = BudgetProvider(FakeProvider(), budget)
    data = {
        "dataset_name": "synthetic",
        "dataset_version": "1",
        "test_case_id": "one",
        "question": "fixture",
        "context": "fixture",
        "expected_answer": "fixture",
    }
    with TestClient(create_app(provider)) as client:
        # Generation is recorded; rate admission refuses judgment without another provider dispatch.
        response = client.post("/evaluations", json=data)
    assert response.status_code == 429
    assert response.json()["detail"]["category"] == "provider_rate_limited"
    assert 1 <= int(response.headers["retry-after"]) <= 60
    assert budget.status()["attempts_reserved"] == 1


async def test_private_runtime_requires_readable_policy_before_sdk_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTEVAL_PRIVATE_SERVER", "1")
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "gemini")
    monkeypatch.setenv("AGENTEVAL_SERVER_BUDGET_DB", str(tmp_path / "missing.sqlite3"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="provider_budget_unavailable"):
        async with provider_context():
            pytest.fail("Unconfigured live provider must not start")


async def test_private_runtime_wraps_non_simulated_stub_without_sdk_calls(tmp_path, monkeypatch):
    path = tmp_path / "budget.sqlite3"
    budget = configure(path, 1, 100, 1)
    monkeypatch.setenv("AGENTEVAL_PRIVATE_SERVER", "1")
    monkeypatch.setenv("AGENTEVAL_SERVER_BUDGET_DB", str(path))
    provider = FakeProvider()
    provider.simulated = False  # Explicitly synthetic stub; no real SDK or human data.
    async with provider_context(provider) as selected:
        assert isinstance(selected, BudgetProvider)
        await selected.generate(
            GenerationInput(question="fixture", context="fixture", prompt="fixture")
        )
        with pytest.raises(ProviderError, match="provider_budget_exhausted"):
            await selected.generate(None)
    assert budget.status()["attempts_reserved"] == 1


async def test_ledger_never_contains_provider_content(tmp_path):
    budget = configure(tmp_path / "budget.sqlite3", 10, 100, 1)
    response = await BudgetProvider(FakeProvider(), budget).generate(
        GenerationInput(
            question="SENSITIVE QUESTION FIXTURE",
            context="SENSITIVE ANSWER FIXTURE",
            prompt="SENSITIVE PROMPT FIXTURE",
        )
    )
    assert response.text == "SENSITIVE ANSWER FIXTURE"
    assert b"SENSITIVE" not in budget.path.read_bytes()
    status = budget.status()
    assert set(status) == {
        "attempt_ceiling",
        "requests_per_minute",
        "concurrency",
        "attempts_reserved",
        "active_or_uncertain",
        "attempts_remaining",
    }
    assert "key" not in json.dumps(status)
    assert os.stat(budget.path).st_mode & 0o077 == 0


def test_reconciliation_and_snapshot_preserve_spent_attempts(tmp_path):
    import sqlite3

    budget = configure(tmp_path / "budget.sqlite3", 10, 100, 1)
    identifier = budget.reserve("embed")
    assert budget.active()[0]["id"] == identifier
    with pytest.raises(ProviderError):
        budget.reconcile(["unknown"])
    budget.reconcile([identifier])
    assert budget.status()["attempts_reserved"] == 1
    assert budget.status()["active_or_uncertain"] == 0
    with sqlite3.connect(":memory:") as recovered:
        recovered.deserialize(budget.snapshot())
        assert recovered.execute("SELECT count(*) FROM attempts").fetchone() == (1,)


@pytest.mark.parametrize("missing", [False, True])
def test_exhausted_or_missing_budget_blocks_http_before_dispatch(tmp_path, missing):
    path = tmp_path / "budget.sqlite3"
    budget = configure(path, 1, 100, 1)
    ticket = budget.reserve("generate")
    budget.finish(ticket, None, True)
    if missing:
        path.unlink()
    provider = FakeProvider()
    provider.generate = AsyncMock()
    with TestClient(create_app(BudgetProvider(provider, budget))) as client:
        response = client.post(
            "/evaluations",
            json={
                "dataset_name": "synthetic",
                "dataset_version": "1",
                "test_case_id": "one",
                "question": "fixture",
                "expected_answer": "fixture",
            },
        )
    assert response.status_code == (503 if missing else 429)
    provider.generate.assert_not_awaited()
    assert str(path) not in response.text
