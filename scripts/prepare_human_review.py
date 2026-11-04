"""Prepare a shuffled review packet without category hints or generated labels."""

import json
import os
import random
from pathlib import Path

root = Path(__file__).resolve().parents[1]
examples = json.loads((root / "examples/judge_study.json").read_text())
labels = json.loads((root / "examples/human_labels.template.json").read_text())
assert len(examples) == len(labels) == 50
assert {r["example_id"] for r in examples} == {r["example_id"] for r in labels}
assert all(row["human_pass"] is None for row in labels)
packet = [
    {key: row[key] for key in ("example_id", "question", "expected_answer", "context", "response")}
    for row in examples
]
random.Random(42).shuffle(packet)
folder = root / "artifacts"
folder.mkdir(exist_ok=True)
for name, value in [
    ("human_review_packet.json", {"rubric_version": "v1", "examples": packet}),
    ("human_labels.json", labels),
]:
    path = folder / name
    if path.exists():
        print(f"Preserved existing artifacts/{name}")
        continue
    with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as file:
        json.dump(value, file, indent=2)
        file.write("\n")
    print(f"Prepared artifacts/{name}")
print("Zero labels generated. Review the rubric before supplying actual human labels.")
