"""Human/AI agreement analysis. Unlabeled data never becomes synthetic evidence."""

import json
from pathlib import Path

from pydantic import Field, model_validator

from agenteval.domain import StrictModel


class HumanLabel(StrictModel):
    example_id: str
    human_pass: bool | None = Field(default=None, strict=True)
    labeler: str | None = None
    notes: str | None = None
    rubric_version: str = "v1"

    @model_validator(mode="after")
    def attribution(self):
        if self.human_pass is not None and not self.labeler:
            raise ValueError("A human label requires a labeler identifier")
        return self


def unique(rows, key):
    result = {}
    for row in rows:
        identifier = row[key]
        if identifier in result:
            raise ValueError(f"Duplicate {key}")
        result[identifier] = row
    return result


def agreement(examples, labels, judgments):
    source = unique(examples, "example_id")
    human = unique([HumanLabel.model_validate(row).model_dump() for row in labels], "example_id")
    ai = unique(judgments, "example_id")
    if not set(human).issubset(source) or not set(ai).issubset(source):
        raise ValueError("Labels/judgments reference unknown examples")
    matched, disagreements = [], []
    for key, row in human.items():
        prediction = ai.get(key)
        if row["human_pass"] is None or prediction is None:
            continue
        if row["rubric_version"] != prediction["rubric_version"]:
            raise ValueError("Incompatible rubric versions")
        if type(prediction.get("passed")) is not bool:
            raise ValueError("Judge passed field must be boolean")
        matched.append((row["human_pass"], prediction["passed"]))
        if row["human_pass"] != prediction["passed"]:
            disagreements.append(
                {
                    "example_id": key,
                    "category": source[key]["category"],
                    "human_pass": row["human_pass"],
                    "judge_pass": prediction["passed"],
                }
            )
    tp = sum(h and a for h, a in matched)
    tn = sum(not h and not a for h, a in matched)
    fp = sum(not h and a for h, a in matched)
    fn = sum(h and not a for h, a in matched)

    def ratio(n, d):
        return n / d if d else None

    return {
        "status": "MEASURED" if matched else "BLOCKED",
        "positive_class": "quality_pass",
        "example_count": len(source),
        "human_labeled": sum(r["human_pass"] is not None for r in human.values()),
        "paired_count": len(matched),
        "simulated_judge": any(r.get("simulated", False) for r in ai.values()) if ai else None,
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "agreement": ratio(tp + tn, len(matched)),
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "false_positive_rate": ratio(fp, fp + tn),
        "false_negative_rate": ratio(fn, fn + tp),
        "disagreements": disagreements,
        "limitation": "A small controlled sample is not representative of all LLM applications.",
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--examples", default="examples/judge_study.json")
    parser.add_argument("--labels", default="examples/human_labels.template.json")
    parser.add_argument("--judgments")
    parser.add_argument("--output", default="reports/judge_validation.json")
    args = parser.parse_args()
    report = agreement(
        json.loads(Path(args.examples).read_text()),
        json.loads(Path(args.labels).read_text()),
        json.loads(Path(args.judgments).read_text()) if args.judgments else [],
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "paired_count": report["paired_count"]}))


if __name__ == "__main__":
    main()
