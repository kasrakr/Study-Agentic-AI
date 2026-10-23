"""Structured-output schemas for the agent's LLM calls.

All fields are required (nullable where needed) so the schemas work with
OpenAI strict structured outputs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    intent: Literal["study_question", "explain_simply", "quiz", "flashcards", "smalltalk"]
    wants_web: bool = Field(
        description="True only if the student explicitly asks for external, online or up-to-date information."
    )
    topic: str | None = Field(
        description="For quiz/flashcards: the specific subject requested, else null."
    )
    standalone_question: str = Field(
        description="The student's request rewritten so it makes sense without the chat history."
    )


class DocumentGrade(BaseModel):
    verdict: Literal["sufficient", "partial", "insufficient"]
    reason: str = Field(description="One or two sentences explaining the verdict.")
    relevant_passages: list[int] = Field(description="Numbers of passages that help answer the question.")
    missing_information: list[str] = Field(
        description="Specific parts of the question the passages do not answer. Empty if sufficient."
    )
    retrieval_may_have_missed: bool = Field(
        description="True if a differently worded search of the documents might find better passages."
    )


class MissingInfoPlan(BaseModel):
    missing_information: list[str]
    web_search_query: str = Field(description="A short, generic web search query for the missing part.")


class RewrittenQuery(BaseModel):
    query: str


class WebResultGrade(BaseModel):
    index: int = Field(description="Result number as shown in the prompt.")
    relevant: bool
    reliability: Literal["high", "medium", "low"]


class WebEvidenceGrade(BaseModel):
    results: list[WebResultGrade]
    coverage: Literal["full", "partial", "none"] = Field(
        description="How much of the missing information the relevant results cover."
    )
    reason: str
