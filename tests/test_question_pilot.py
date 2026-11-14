import copy
import json
import runpy
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
module = runpy.run_path(str(ROOT / "scripts/run_question_pilot.py"))
prepare = runpy.run_path(str(ROOT / "scripts/prepare_new_question_study.py"))["prepare"]
execute = module["execute"]
analyze = module["analyze"]


@pytest.fixture
def study(tmp_path):
    folder = tmp_path / "study"
    prepare(ROOT / "examples/judge_new_questions.json", ROOT / "examples/judge_study.json", folder)
    return folder


@pytest.mark.asyncio
async def test_default_plan_never_opens_provider_and_tamper_rejected(study, monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("Provider must not open")

    monkeypatch.setitem(execute.__globals__, "provider_context", forbidden)
    assert (await execute(study, None))["status"] == "PLAN_VALIDATED_NO_CALLS"
    with (study / "fixture.json").open("a") as file:
        file.write(" ")
    with pytest.raises(ValueError, match="hash mismatch"):
        await execute(study, None)


@pytest.mark.asyncio
async def test_unreviewed_labels_refuse_before_output_or_provider(study, tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "gemini")
    output = tmp_path / "results"
    with pytest.raises(ValueError, match="genuine"):
        await execute(study, output, live=True, authorized_attempts=30)
    assert not output.exists()


@pytest.mark.asyncio
async def test_first_failure_stops_all_repetitions_and_keeps_private_snapshot(
    study, tmp_path, monkeypatch
):
    # Explicitly synthetic test decisions, never real study evidence.
    labels = json.loads((study / "human_labels.json").read_text())
    for row in labels:
        row.update(human_pass=False, labeler="synthetic-test")
    (study / "human_labels.json").write_text(json.dumps(labels))
    before = (study / "human_labels.json").read_bytes()
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "gemini")
    calls = []

    @asynccontextmanager
    async def provider(**kwargs):
        yield object()

    async def fail(provider, rows, output, **kwargs):
        calls.append(output)
        output.write_text("[]")
        raise RuntimeError("synthetic provider failure")

    monkeypatch.setitem(execute.__globals__, "provider_context", provider)
    monkeypatch.setitem(execute.__globals__, "collect", fail)
    output = tmp_path / "results"
    with pytest.raises(RuntimeError):
        await execute(study, output, live=True, authorized_attempts=30, delay=0)
    assert len(calls) == 1
    assert (output / "repetition-1.json").exists()
    snapshot = output / "human_labels.frozen.json"
    assert snapshot.read_bytes() == before == (study / "human_labels.json").read_bytes()
    assert snapshot.stat().st_mode & 0o222 == 0
    with pytest.raises(FileExistsError):
        await execute(study, output, live=True, authorized_attempts=30, delay=0)
    assert len(calls) == 1


def predictions(rows):
    return [
        {
            "example_id": r["example_id"],
            "passed": False,
            "rubric_version": "v1",
            "provider": "synthetic",
            "model": "test",
            "simulated": True,
            "judge_prompt_version": "test",
            "judge_prompt_sha256": "test-hash",
        }
        for r in rows
    ]


def test_repeatability_keeps_repetitions_separate(study):
    _, rows = module["load_plan"](study)
    labels = [
        {
            "example_id": r["example_id"],
            "human_pass": False,
            "labeler": "synthetic-test",
            "rubric_version": "v1",
        }
        for r in rows
    ]
    reps = [predictions(rows) for _ in range(3)]
    reps[2][0]["passed"] = True
    report = analyze(rows, labels, reps)
    assert report["status"] == "SIMULATED_REHEARSAL"
    assert report["distinct_questions"] == 5
    assert report["stable_response_count"] == 9
    assert report["decision_changes_across_repetitions"] == [rows[0]["example_id"]]
    assert [r["agreement"] for r in report["repetition_reports"]] == [1, 1, 0.9]
    invalid = copy.deepcopy(reps)
    invalid[1][0]["model"] = "different"
    with pytest.raises(ValueError, match="configuration"):
        analyze(rows, labels, invalid)
    with pytest.raises(ValueError, match="exact frozen IDs"):
        analyze(rows, labels, [reps[0], reps[1], reps[2][:-1]])
