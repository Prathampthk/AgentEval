import pytest

from agenteval.judge_validation import agreement


def test_confusion_matrix_and_rates():
    examples = [{"example_id": str(i), "category": "controlled"} for i in range(4)]
    labels = [
        {"example_id": str(i), "human_pass": v, "labeler": "unit-test fixture"}
        for i, v in enumerate([True, True, False, False])
    ]
    judges = [
        {"example_id": str(i), "passed": v, "rubric_version": "v1", "simulated": True}
        for i, v in enumerate([True, False, True, False])
    ]
    report = agreement(examples, labels, judges)
    assert report["confusion_matrix"] == dict(tp=1, tn=1, fp=1, fn=1)
    assert report["agreement"] == report["precision"] == report["recall"] == 0.5
    assert report["false_positive_rate"] == report["false_negative_rate"] == 0.5
    assert report["simulated_judge"] and len(report["disagreements"]) == 2


def test_unlabeled_report_has_no_fabricated_accuracy():
    report = agreement([{"example_id": "a", "category": "test"}], [], [])
    assert report["status"] == "BLOCKED" and report["paired_count"] == 0
    assert report["agreement"] is None and report["false_positive_rate"] is None


def test_unknown_and_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        agreement([], [{"example_id": "unknown"}], [])
    with pytest.raises(ValueError):
        agreement([{"example_id": "a"}] * 2, [], [])


def test_unattributed_human_label_rejected():
    with pytest.raises(ValueError):
        agreement([{"example_id": "a"}], [{"example_id": "a", "human_pass": True}], [])


@pytest.mark.parametrize(
    "field,values",
    [
        ("judge_prompt_version", ["v1", "candidate-v2"]),
        ("judge_prompt_sha256", ["old-prompt-hash", "new-prompt-hash"]),
    ],
)
def test_mixed_judge_prompts_rejected(field, values):
    examples = [dict(example_id=str(i)) for i in range(2)]
    judgments = [
        dict(example_id=str(i), rubric_version="v1", passed=False, **{field: value})
        for i, value in enumerate(values)
    ]
    with pytest.raises(ValueError, match="Mixed judge prompts"):
        agreement(examples, [], judgments)
