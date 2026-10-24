"""Evaluation dataset: evals/questions.jsonl plus the sample documents in evals/documents/."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from app.config import PROJECT_ROOT

EVALS_DIR = PROJECT_ROOT / "evals"


class EvalQuestion(BaseModel):
    id: str
    category: str  # covered | exact_term | partial | not_covered | explicit_external
    question: str
    expected_documents: list[str]  # filenames in evals/documents; empty = nothing in the documents answers it
    needs_web: bool  # should the agent use web search for this question?
    reference_answer: str
    key_facts: list[str]


def load_questions(path: Path | None = None) -> list[EvalQuestion]:
    path = path or EVALS_DIR / "questions.jsonl"
    questions = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            try:
                questions.append(EvalQuestion.model_validate(json.loads(line)))
            except Exception as exc:
                raise ValueError(f"{path.name} line {n}: {exc}") from exc
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate question ids in dataset.")
    return questions
