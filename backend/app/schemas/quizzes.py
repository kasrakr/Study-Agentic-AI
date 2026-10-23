from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

QuestionType = Literal["multiple_choice", "true_false", "short_answer"]
Difficulty = Literal["easy", "medium", "hard"]


# ---------------- LLM draft output (validated again in code) ----------------

class QuizQuestionDraft(BaseModel):
    type: QuestionType
    question: str
    options: list[str] = Field(description="Exactly 4 options for multiple_choice, otherwise empty.")
    correct_option_index: int | None = Field(description="0-based index for multiple_choice, else null.")
    correct_boolean: bool | None = Field(description="Answer for true_false, else null.")
    reference_answer: str | None = Field(description="Model answer for short_answer, else null.")
    key_points: list[str] = Field(description="2-4 rubric points for short_answer, otherwise empty.")
    explanation: str
    source_number: int = Field(description="Number of the passage this question is based on.")
    topic: str = Field(description="Short topic label (2-4 words).")


class QuizDraft(BaseModel):
    questions: list[QuizQuestionDraft]


class ItemGrade(BaseModel):
    item: int
    key_point_results: list[bool] = Field(description="One boolean per rubric key point, in order.")
    feedback: str


class ShortAnswerGrades(BaseModel):
    grades: list[ItemGrade]


# ---------------- API ----------------

class QuizGenerateRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1, max_length=20)
    question_count: int = Field(default=5, ge=1, le=50)
    question_types: list[QuestionType] = Field(default=["multiple_choice"], min_length=1)
    difficulty: Difficulty = "medium"
    topic: str | None = Field(default=None, max_length=200)

    @field_validator("question_types")
    @classmethod
    def _unique_types(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))

    @field_validator("topic")
    @classmethod
    def _blank_topic_is_none(cls, v: str | None) -> str | None:
        return v.strip() or None if v else None


class QuizQuestionOut(BaseModel):
    """What the student sees before submitting: no answer key, no explanation."""

    id: str
    position: int
    type: QuestionType
    question: str
    options: list[str]
    topic: str


class QuizOut(BaseModel):
    id: str
    title: str
    difficulty: Difficulty
    document_ids: list[str]
    question_count: int
    created_at: datetime
    questions: list[QuizQuestionOut]


class AnswerIn(BaseModel):
    question_id: str
    selected_option: int | None = Field(default=None, ge=0, le=9)  # multiple_choice
    boolean_answer: bool | None = None  # true_false
    text_answer: str | None = Field(default=None, max_length=4000)  # short_answer


class QuizSubmitRequest(BaseModel):
    answers: list[AnswerIn] = Field(max_length=50)

    @model_validator(mode="after")
    def _no_duplicates(self) -> "QuizSubmitRequest":
        ids = [a.question_id for a in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("each question may be answered only once")
        return self


class SourceRef(BaseModel):
    document_id: str
    filename: str
    page_number: int | None


class QuestionResult(BaseModel):
    question_id: str
    position: int
    type: QuestionType
    question: str
    options: list[str]
    topic: str
    your_answer: str | None
    correct_answer: str
    is_correct: bool | None  # None when unanswered
    points: float
    max_points: float = 1.0
    graded_by: Literal["auto", "model", "unanswered"]
    feedback: str | None
    explanation: str
    source: SourceRef


class AttemptResult(BaseModel):
    attempt_id: str
    quiz_id: str
    points: float
    max_points: float
    score_percent: float
    graded_by_model: bool
    grading_note: str | None
    results: list[QuestionResult]
