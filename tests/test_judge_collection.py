"""Offline checks for bounded requests, evidence preservation and partial results."""

import json
import runpy
import sys
from pathlib import Path

import pytest

from agenteval.domain import JudgeResponse, Judgment, Usage
from agenteval.providers import ProviderError

script = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/judge_examples.py"))
collect = script["collect"]
select_examples = script["select_examples"]


def examples(n):
    return [
        dict(example_id=str(i), question="q", expected_answer="a", context="a", response="a")
        for i in range(n)
    ]


class StubJudge:
    name = "offline-stub"
    model = "test-only"
    simulated = False

    def __init__(self, fail_on=None):
        self.calls = 0
        self.fail_on = fail_on

    async def judge(self, data):
        self.calls += 1
        if self.calls == self.fail_on:
            raise ProviderError("rate_limit", True)
        return JudgeResponse(
            judgment=Judgment(correctness=2, relevance=2, groundedness=2, explanation="fixture"),
            usage=Usage(input_tokens=12, output_tokens=5),
        )


async def test_success_saves_usage_and_reproducible_metadata(tmp_path):
    provider = StubJudge()
    output = tmp_path / "predictions.json"
    rows = await collect(provider, examples(2), output)
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    assert provider.calls == 2 and json.loads(output.read_text()) == rows
    assert rows[0]["usage"] == dict(input_tokens=12, output_tokens=5)
    assert metadata["status"] == "COMPLETED" and metadata["requests_started"] == 2
    assert metadata["responses_saved"] == 2 and not metadata["billing_tier_verified"]
    assert all("human_pass" not in row for row in rows)


async def test_failure_stops_without_retry_and_preserves_success(tmp_path):
    provider = StubJudge(fail_on=2)
    output = tmp_path / "predictions.json"
    with pytest.raises(ProviderError):
        await collect(provider, examples(3), output)
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    assert provider.calls == 2 and len(json.loads(output.read_text())) == 1
    assert metadata["status"] == "STOPPED" and metadata["error_category"] == "rate_limit"
    assert metadata["requests_started"] == 2 and metadata["responses_saved"] == 1


@pytest.mark.parametrize("existing", ["predictions.json", "predictions.meta.json"])
async def test_existing_evidence_refused_before_calls(tmp_path, existing):
    path = tmp_path / existing
    path.write_text("preserve")
    provider = StubJudge()
    with pytest.raises(FileExistsError):
        await collect(provider, examples(1), tmp_path / "predictions.json")
    assert provider.calls == 0 and path.read_text() == "preserve"


async def test_live_cap_checked_before_any_call_or_file(tmp_path):
    provider = StubJudge()
    with pytest.raises(ValueError):
        await collect(provider, examples(11), tmp_path / "predictions.json")
    assert provider.calls == 0 and not list(tmp_path.iterdir())


def test_selection_deterministic_without_mutating_source():
    source = examples(50)
    before = list(source)
    selected = select_examples(source, 10, 42)
    assert selected == select_examples(source, 10, 42)
    assert len({r["example_id"] for r in selected}) == 10
    assert source == before and selected != source[:10]


@pytest.mark.parametrize("offset,limit", [(0, 10), (4, 6), (10, 10)])
async def test_offline_plan_never_constructs_provider(tmp_path, monkeypatch, offset, limit):
    output = tmp_path / "plan.json"
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "judge_examples.py",
            "--plan",
            "--offset",
            str(offset),
            "--limit",
            str(limit),
            "--output",
            str(output),
        ],
    )

    def forbidden_provider():
        pytest.fail("Offline planning must never construct a provider")

    monkeypatch.setitem(script["main"].__globals__, "provider_context", forbidden_provider)
    await script["main"]()
    plan = json.loads(output.read_text())
    assert plan["provider_calls"] == 0 and len(plan["selected_ids"]) == limit
    source = json.loads(
        (Path(__file__).resolve().parents[1] / "examples/judge_study.json").read_text()
    )
    assert plan["selected_ids"] == [
        row["example_id"]
        for row in select_examples(source, offset + limit, 42)[offset : offset + limit]
    ]


async def test_live_flag_required_before_provider_setup(tmp_path, monkeypatch):
    output = tmp_path / "predictions.json"
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "gemini")
    monkeypatch.setattr(sys, "argv", ["judge_examples.py", "--output", str(output)])
    with pytest.raises(SystemExit) as exc:
        await script["main"]()
    assert exc.value.code == 2 and not output.exists()
