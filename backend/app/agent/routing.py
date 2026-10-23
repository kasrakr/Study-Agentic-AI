"""Pure routing functions for the graph's conditional edges (unit-tested directly)."""

from __future__ import annotations

from app.agent.state import AgentState


def route_after_classify(state: AgentState) -> str:
    intent = state.get("intent")
    if intent == "smalltalk":
        return "respond_smalltalk"
    if intent == "quiz":
        return "generate_quiz"
    if intent == "flashcards":
        return "generate_flashcards"
    return "retrieve_documents"


def route_after_document_grade(state: AgentState, *, max_retries: int) -> str:
    """Document-first decision.

    - Student explicitly wants external info -> web fallback (documents were still searched first).
    - Evidence sufficient -> answer from documents; the web is never touched.
    - Evidence weak/partial and a better query might help (and retries remain) -> rewrite once.
    - Otherwise -> find what's missing and search the web for just that.
    """
    if state.get("wants_web"):
        return "identify_missing_information"
    if state.get("evidence_verdict") == "sufficient":
        return "generate_answer"
    can_retry = (
        state.get("retrieval_may_have_missed", False)
        and state.get("retry_count", 0) < max_retries
        and bool(state.get("retrieved_document_chunks"))
    )
    return "rewrite_query" if can_retry else "identify_missing_information"


def route_after_rewrite(state: AgentState) -> str:
    # If the rewrite found nothing new, searching again would return the same chunks.
    return "retrieve_documents" if state.get("query_changed") else "identify_missing_information"
