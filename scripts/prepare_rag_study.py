"""Freeze an offline RAG plan and unanswered human-review template; never call a provider."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from pydantic import Field, model_validator

from agenteval.domain import StrictModel
from agenteval.rag import DocumentCreate, RagQuestion, chunk


class StudyDocument(DocumentCreate):
    id: str = Field(min_length=1)


class StudyQuestion(RagQuestion):
    id: str = Field(min_length=1)
    expected_answer: str | None = Field(default=None, min_length=1, max_length=4000)
    expected_document_ids: list[str]


class Study(StrictModel):
    version: str = Field(min_length=1)
    scope: str
    documents: list[StudyDocument] = Field(min_length=1)
    questions: list[StudyQuestion] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ground_truth(self):
        ids = {d.id for d in self.documents}
        if len(ids) != len(self.documents) or len({q.id for q in self.questions}) != len(
            self.questions
        ):
            raise ValueError("Duplicate study identifiers")
        for q in self.questions:
            expected = set(q.expected_document_ids)
            if len(expected) != len(q.expected_document_ids) or not expected <= ids:
                raise ValueError("Unknown or duplicate expected documents")
            if bool(expected) != (q.expected_answer is not None):
                raise ValueError("Answerable questions require evidence and an expected answer")
            if len(expected) > q.k:
                raise ValueError("Expected document count exceeds retrieval k")
        return self


def prepare(source, output):
    raw = source.read_bytes()
    study = Study.model_validate_json(raw)
    # A fresh directory prevents partial overwrites of prior plans or human work.
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    answerable = [q for q in study.questions if q.expected_answer is not None]
    embeddings = sum(len(chunk(d.content)) for d in study.documents)
    plan = {
        "status": "PREPARED_OFFLINE",
        "study_version": study.version,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "live_execution_authorized": False,
        "provider_calls_made": 0,
        "human_labels_created": 0,
        "document_count": len(study.documents),
        "question_ids": [q.id for q in study.questions],
        "answerable_questions": len(answerable),
        "unanswerable_questions": len(study.questions) - len(answerable),
        "planned_successful_path_operations": {
            "document_embeddings": embeddings,
            "query_embeddings": len(study.questions),
            "generations": len(study.questions),
            "judgments": len(answerable),
            "total": embeddings + 2 * len(study.questions) + len(answerable),
        },
        "execution_notes": [
            "Use a fresh isolated corpus; resolve fixture document IDs to returned database IDs.",
            "Answerable questions use /rag/evaluate; unanswerable questions use /rag/ask.",
            "Recall/Hit Rate are undefined for unanswerable questions; report them as null.",
            "Review abstention, answer support and citations manually; leave human decisions null until reviewed.",
            "The successful-path count excludes failed, retried or repeated requests and is not a cost ceiling.",
            "Agree a separate request budget and pacing before implementing or running live collection.",
        ],
    }
    review = {
        "study_version": study.version,
        "source_sha256": plan["source_sha256"],
        "instructions": "Populate from separately collected answers and supplied evidence before human review. Never infer human labels from fixture answers or judge scores.",
        "reviews": [
            {
                "question_id": q.id,
                "question": q.question,
                "answer": None,
                "supplied_evidence": None,
                "answer_supported": None,
                "citations_supported": None,
                "appropriate_abstention": None,
                "reviewer": None,
                "notes": None,
            }
            for q in study.questions
        ],
    }
    for name, value in (
        ("plan.json", plan),
        ("human_review.json", review),
    ):
        with open(
            output / name, "x", opener=lambda path, flags: os.open(path, flags, 0o600)
        ) as file:
            file.write(json.dumps(value, indent=2) + "\n")
    with open(
        output / "fixture.json", "xb", opener=lambda path, flags: os.open(path, flags, 0o600)
    ) as file:
        file.write(raw)
    return plan


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "examples/rag_study.json")
    parser.add_argument("--output-dir", type=Path, default=root / "artifacts/rag-study-v1")
    args = parser.parse_args()
    try:
        plan = prepare(args.source, args.output_dir)
    except (OSError, ValueError) as exc:
        parser.error(
            f"Preparation stopped ({type(exc).__name__}); use a fresh output directory and valid fixture"
        )
    print(
        f"Prepared {len(plan['question_ids'])} questions; no provider calls or human labels. Plan: {args.output_dir / 'plan.json'}"
    )


if __name__ == "__main__":
    main()
