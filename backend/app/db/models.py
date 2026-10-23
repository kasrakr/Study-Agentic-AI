"""ORM models. Quiz/progress tables are added in later phases."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db.database import Base

STATUS_PROCESSING = "processing"
STATUS_INDEXED = "indexed"
STATUS_FAILED = "failed"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Store UTC datetimes; SQLite drops tzinfo, so re-attach it on read."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):  # noqa: ANN001
        return None if value is None else value.replace(tzinfo=timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    # Stable id derived from the file's SHA-256 ("doc_" + first 16 hex chars),
    # so uploading identical bytes twice cannot create a second index entry.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))  # sanitized display name
    file_type: Mapped[str] = mapped_column(String(16))  # pdf | txt | md
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    stored_filename: Mapped[str] = mapped_column(String(64))  # internal, never user-supplied
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_PROCESSING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    indexed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Conversation(Base):
    """Listing metadata only. Messages live in the LangGraph checkpoint, keyed by
    thread_id == conversation id, so conversations never share state."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# ---------------------------------------------------------------- quizzes

class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    difficulty: Mapped[str] = mapped_column(String(16))
    document_ids: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    quiz_id: Mapped[str] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(20))  # multiple_choice | true_false | short_answer
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)  # [] for short_answer
    # {"correct_option_index": int} | {"correct": bool} | {"reference_answer": str, "key_points": [str]}
    answer_key: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(120))
    # Source reference, copied at generation time so it survives document deletion.
    document_id: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_id: Mapped[str] = mapped_column(String(80))


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    quiz_id: Mapped[str] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    points: Mapped[float] = mapped_column(Float)
    max_points: Mapped[float] = mapped_column(Float)
    score_percent: Mapped[float] = mapped_column(Float)
    graded_by_model: Mapped[bool] = mapped_column(Boolean, default=False)


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("quiz_questions.id", ondelete="CASCADE"), index=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)  # what the student answered, as text
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None = unanswered
    points: Mapped[float] = mapped_column(Float)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    graded_by: Mapped[str] = mapped_column(String(12))  # auto | model | unanswered


# ---------------------------------------------------------------- flashcards

class FlashcardDeck(Base):
    __tablename__ = "flashcard_decks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    document_ids: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("flashcard_decks.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(120))
    document_id: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_id: Mapped[str] = mapped_column(String(80))
    difficulty: Mapped[str | None] = mapped_column(String(10), nullable=True)  # easy | medium | difficult
    rated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
