"""Shared LangGraph state.

Everything stored here must be JSON-serializable because the SQLite
checkpointer persists it. Retrieved chunks are therefore plain dicts.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

RESET = "__reset__"


def merge_events(left: list[dict] | None, right: list[dict] | None) -> list[dict]:
    """Append events; a leading {"step": RESET} entry clears the previous turn's events.

    The checkpointer keeps state per conversation, so without this the timeline
    of one question would pile up on top of the previous question's.
    """
    right = right or []
    if right and right[0].get("step") == RESET:
        return list(right[1:])
    return [*(left or []), *right]


class AgentState(TypedDict, total=False):
    # --- input ---
    question: str
    thread_id: str
    selected_document_ids: list[str] | None
    # --- classification ---
    intent: str  # study_question | explain_simply | quiz | flashcards | smalltalk
    wants_web: bool  # student explicitly asked for external / up-to-date information
    study_tool_topic: str | None  # topic for quiz / flashcards
    standalone_question: str  # question rewritten to make sense without chat history
    retrieval_query: str
    # --- document retrieval and grading ---
    retrieved_document_chunks: list[dict[str, Any]]
    document_sources: list[dict[str, Any]]  # chunks used for the answer, with markers D1, D2...
    evidence_verdict: str  # sufficient | partial | insufficient
    evidence_sufficient: bool
    evidence_reason: str
    retrieval_may_have_missed: bool
    missing_information: list[str]
    retry_count: int
    query_changed: bool
    # --- web fallback ---
    web_search_query: str
    web_search_results: list[dict[str, Any]]
    web_sources: list[dict[str, Any]]  # results that passed grading, with markers W1, W2...
    web_search_used: bool  # a search request was actually sent
    web_search_error: str | None
    web_coverage: str  # full | partial | none
    # --- output ---
    final_answer: str
    answer_sources: list[dict[str, Any]]  # validated citations
    answer_origin: str  # documents | web | documents_and_web | none
    limitations: str | None
    artifact: dict[str, Any] | None  # generated quiz / flashcard deck reference
    error: dict[str, Any] | None
    execution_events: Annotated[list[dict[str, Any]], merge_events]
    messages: Annotated[list[BaseMessage], add_messages]


def initial_turn_state(
    question: str, thread_id: str, document_ids: list[str] | None
) -> AgentState:
    """Fresh per-turn fields. `messages` is deliberately omitted so conversation
    history carries over from the checkpoint."""
    return {
        "question": question,
        "thread_id": thread_id,
        "selected_document_ids": document_ids or None,
        "intent": "study_question",
        "wants_web": False,
        "study_tool_topic": None,
        "standalone_question": question,
        "retrieval_query": question,
        "retrieved_document_chunks": [],
        "document_sources": [],
        "evidence_verdict": "insufficient",
        "evidence_sufficient": False,
        "evidence_reason": "",
        "retrieval_may_have_missed": False,
        "missing_information": [],
        "retry_count": 0,
        "query_changed": False,
        "web_search_query": "",
        "web_search_results": [],
        "web_sources": [],
        "web_search_used": False,
        "web_search_error": None,
        "web_coverage": "none",
        "final_answer": "",
        "answer_sources": [],
        "answer_origin": "none",
        "limitations": None,
        "artifact": None,
        "error": None,
        "execution_events": [{"step": RESET}],
    }
