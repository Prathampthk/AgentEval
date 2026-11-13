import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
prepare = runpy.run_path(str(ROOT / "scripts/prepare_new_question_study.py"))["prepare"]
SOURCE = ROOT / "examples/judge_new_questions.json"
PREVIOUS = ROOT / "examples/judge_study.json"


def test_packet_preserves_unanswered_decisions_and_refuses_overwrite(tmp_path):
    output = tmp_path / "study"
    plan = prepare(SOURCE, PREVIOUS, output)
    assert plan["distinct_questions"] == 5
    assert plan["proposed_judge_operations"] == 30
    assert plan["live_execution_authorized"] is False
    assert plan["provider_calls"] == plan["human_decisions_generated"] == 0
    packet = json.loads((output / "human_review_packet.json").read_text())
    labels = json.loads((output / "human_labels.json").read_text())
    assert len(packet["examples"]) == len(labels) == 10
    assert all("category" not in r for r in packet["examples"])
    assert all(r["human_pass"] is r["labeler"] is r["notes"] is None for r in labels)
    assert (output / "fixture.json").read_bytes() == SOURCE.read_bytes()
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(FileExistsError):
        prepare(SOURCE, PREVIOUS, output)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


@pytest.mark.parametrize("case", ["duplicate", "overlap", "reference", "empty"])
def test_invalid_study_is_rejected_before_output(tmp_path, case):
    rows = json.loads(SOURCE.read_text())
    if case == "duplicate":
        rows[1]["example_id"] = rows[0]["example_id"]
    elif case == "overlap":
        rows[0]["question"] = "  " + json.loads(PREVIOUS.read_text())[0]["question"].upper()
    elif case == "reference":
        rows[1]["expected_answer"] = "conflicting reference"
    else:
        rows[0]["context"] = " "
    source = tmp_path / "source.json"
    source.write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        prepare(source, PREVIOUS, tmp_path / "output")
    assert not (tmp_path / "output").exists()
