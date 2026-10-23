from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_CONVERSATION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    # Restrict retrieval to these documents. Omit to search all indexed documents.
    document_ids: list[str] | None = Field(default=None, max_length=50)

    @field_validator("question")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value

    @field_validator("conversation_id")
    @classmethod
    def _check_conversation_id(cls, value: str | None) -> str | None:
        if value is not None and not _CONVERSATION_ID.match(value):
            raise ValueError("conversation_id must be 1-64 letters, digits, '_' or '-'")
        return value


class Citation(BaseModel):
    """A source the answer relies on. Built only from retrieved metadata,
    never from model-generated text."""

    source_type: Literal["document"] = "document"
    source_number: int  # matches the [n] markers in the answer
    document_id: str
    filename: str
    page_number: int | None
    chunk_id: str
    snippet: str
    score: float


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[Citation]
    # Steps that actually ran, in order (e.g. ["retrieve_documents", "generate_answer"]).
    retrieval_path: list[str]
    evidence_found: bool
    limitations: str | None
    retrieved_count: int
    latency_ms: int
