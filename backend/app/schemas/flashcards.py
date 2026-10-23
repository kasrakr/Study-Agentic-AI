from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CardDifficulty = Literal["easy", "medium", "difficult"]


class FlashcardDraft(BaseModel):
    front: str = Field(description="A question or concept.")
    back: str = Field(description="The answer or explanation.")
    source_number: int
    topic: str = Field(description="Short topic label (2-4 words).")


class FlashcardSet(BaseModel):
    cards: list[FlashcardDraft]


class FlashcardGenerateRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1, max_length=20)
    card_count: int = Field(default=10, ge=1, le=100)
    topic: str | None = Field(default=None, max_length=200)

    @field_validator("topic")
    @classmethod
    def _blank_topic_is_none(cls, v: str | None) -> str | None:
        return v.strip() or None if v else None


class FlashcardOut(BaseModel):
    id: str
    position: int
    front: str
    back: str
    topic: str
    document_id: str
    filename: str
    page_number: int | None
    difficulty: CardDifficulty | None
    rated_at: datetime | None


class DeckOut(BaseModel):
    id: str
    title: str
    document_ids: list[str]
    created_at: datetime
    cards: list[FlashcardOut]


class RateCardRequest(BaseModel):
    difficulty: CardDifficulty
