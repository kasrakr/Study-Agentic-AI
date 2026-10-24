from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RecentAttempt(BaseModel):
    attempt_id: str
    quiz_id: str
    quiz_title: str
    score_percent: float
    points: float
    max_points: float
    graded_by_model: bool
    submitted_at: datetime


class QuizStats(BaseModel):
    attempts: int
    average_score_percent: float | None
    best_score_percent: float | None
    recent: list[RecentAttempt]


class FlashcardStats(BaseModel):
    decks: int
    rated: int
    easy: int
    medium: int
    difficult: int


class DocumentRef(BaseModel):
    document_id: str
    filename: str


class WeakTopic(BaseModel):
    topic: str
    data_points: int  # answered quiz questions + rated flashcards on this topic
    incorrect_answers: int
    difficult_cards: int
    weak_share: float  # (incorrect + difficult) / data_points
    documents: list[DocumentRef]  # source documents that still exist


class Suggestion(BaseModel):
    kind: Literal["practice_quiz"]
    topic: str
    document_ids: list[str]
    reason: str


class ActivityItem(BaseModel):
    type: Literal["upload", "chat", "quiz", "flashcards"]
    title: str
    at: datetime
    ref_id: str


class ProgressOut(BaseModel):
    indexed_documents: int
    quiz: QuizStats
    flashcards: FlashcardStats
    weak_topics: list[WeakTopic]
    weak_topics_method: str
    weak_topics_note: str | None  # shown when there is too little data to flag anything
    suggestions: list[Suggestion]
    recent_activity: list[ActivityItem]
