from __future__ import annotations

import re
from datetime import datetime
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
    """A source the answer relies on. Built only from retrieved metadata or real
    search results, never from model-generated text."""

    source_type: Literal["document", "web"]
    marker: str  # "D1" / "W1": matches the [D1] / [W1] markers in the answer
    snippet: str
    score: float | None = None
    # Document sources
    document_id: str | None = None
    filename: str | None = None
    page_number: int | None = None
    chunk_id: str | None = None
    # Web sources
    title: str | None = None
    url: str | None = None


class ExecutionEvent(BaseModel):
    """One step that actually ran. Never contains model reasoning."""

    step: str
    detail: str | None = None
    duration_ms: int | None = None


class Artifact(BaseModel):
    type: Literal["quiz", "flashcards"]
    id: str


class ChatResponse(BaseModel):
    conversation_id: str
    intent: str
    answer: str
    citations: list[Citation]
    answer_origin: Literal["documents", "web", "documents_and_web", "none"]
    # Steps that ran, in order (repeats show a retry).
    retrieval_path: list[str]
    execution_events: list[ExecutionEvent]
    evidence_found: bool
    web_search_used: bool  # a web request was actually sent
    web_search_error: str | None
    limitations: str | None
    artifact: Artifact | None = None
    latency_ms: int


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationList(BaseModel):
    conversations: list[ConversationSummary]


class StoredMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    # Assistant messages only:
    citations: list[Citation] = []
    answer_origin: str | None = None
    retrieval_path: list[str] = []
    web_search_used: bool = False
    limitations: str | None = None
    artifact: Artifact | None = None


class ConversationDetail(BaseModel):
    conversation: ConversationSummary
    messages: list[StoredMessage]
