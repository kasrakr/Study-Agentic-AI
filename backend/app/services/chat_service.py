"""Runs the LangGraph agent and exposes results as API objects / SSE events."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

from sqlalchemy import select

from app.agent.state import initial_turn_state
from app.errors import AppError, NotFoundError
from app.db.models import Conversation, utcnow
from app.schemas.chat import (
    Artifact,
    ChatResponse,
    Citation,
    ConversationDetail,
    ConversationSummary,
    ExecutionEvent,
    StoredMessage,
)

logger = logging.getLogger(__name__)

# Graph step -> SSE status name.
STATUS_NAMES = {
    "classify_intent": "classifying_question",
    "retrieve_documents": "retrieving_documents",
    "grade_document_evidence": "evaluating_evidence",
    "rewrite_query": "rewriting_query",
    "identify_missing_information": "identifying_missing_information",
    "web_search": "searching_web",
    "grade_web_evidence": "evaluating_web_results",
    "generate_answer": "generating_answer",
    "respond_smalltalk": "responding",
    "generate_quiz": "generating_quiz",
    "generate_flashcards": "generating_flashcards",
}


class ChatService:
    def __init__(self, graph: Any, checkpointer: Any, session_factory: Any) -> None:
        self.graph = graph
        self.checkpointer = checkpointer
        self.session_factory = session_factory
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

    @staticmethod
    def _config(conversation_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": conversation_id}}

    # ---------------------------------------------------------- running
    def answer(self, question: str, conversation_id: str | None, document_ids: list[str] | None) -> ChatResponse:
        cid = conversation_id or uuid.uuid4().hex
        started = time.perf_counter()
        with self._locks[cid]:  # one turn at a time per conversation
            values = self.graph.invoke(initial_turn_state(question, cid, document_ids), self._config(cid))
        self._touch_conversation(cid, question)
        return self._response(cid, values, started)

    def stream(
        self, question: str, conversation_id: str | None, document_ids: list[str] | None
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Yield (event, data) pairs: status*, token*, sources, done  -or-  error."""
        cid = conversation_id or uuid.uuid4().hex
        started = time.perf_counter()
        config = self._config(cid)
        try:
            with self._locks[cid]:
                for mode, payload in self.graph.stream(
                    initial_turn_state(question, cid, document_ids), config, stream_mode=["custom"]
                ):
                    if mode != "custom":
                        continue
                    if payload.get("type") == "token":
                        yield "token", {"text": payload["text"]}
                    elif payload.get("type") == "status":
                        yield "status", {
                            "status": STATUS_NAMES.get(payload["step"], payload["step"]),
                            "step": payload["step"], "phase": payload["phase"],
                            "detail": payload.get("detail"), "duration_ms": payload.get("duration_ms"),
                        }
                values = self.graph.get_state(config).values
        except AppError as exc:
            yield "error", {"code": exc.code, "message": exc.message, "retryable": exc.retryable}
            return
        except Exception:  # noqa: BLE001 - never leak internals to the client
            logger.exception("Streaming chat failed")
            yield "error", {"code": "internal_error", "message": "An unexpected error occurred.", "retryable": False}
            return

        self._touch_conversation(cid, question)
        resp = self._response(cid, values, started)
        yield "sources", {
            # The final, validated text: invalid [n] markers removed. The UI should replace streamed text with this.
            "answer": resp.answer,
            "citations": [c.model_dump() for c in resp.citations],
            "answer_origin": resp.answer_origin,
            "web_search_used": resp.web_search_used,
            "web_search_error": resp.web_search_error,
            "limitations": resp.limitations,
        }
        yield "done", {
            "conversation_id": cid, "intent": resp.intent, "retrieval_path": resp.retrieval_path,
            "execution_events": [e.model_dump() for e in resp.execution_events],
            "evidence_found": resp.evidence_found, "artifact": resp.artifact.model_dump() if resp.artifact else None,
            "latency_ms": resp.latency_ms,
        }

    def _response(self, cid: str, values: dict[str, Any], started: float) -> ChatResponse:
        events = [
            ExecutionEvent(step=e["step"], detail=e.get("detail"), duration_ms=e.get("duration_ms"))
            for e in values.get("execution_events", [])
        ]
        citations = [Citation(**c) for c in values.get("answer_sources", [])]
        artifact = values.get("artifact")
        return ChatResponse(
            conversation_id=cid,
            intent=values.get("intent", "study_question"),
            answer=values.get("final_answer", ""),
            citations=citations,
            answer_origin=values.get("answer_origin", "none"),
            retrieval_path=[e.step for e in events],
            execution_events=events,
            evidence_found=bool(citations) or bool(artifact),
            web_search_used=values.get("web_search_used", False),
            web_search_error=values.get("web_search_error"),
            limitations=values.get("limitations"),
            artifact=Artifact(**artifact) if artifact else None,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    # ---------------------------------------------------------- conversations
    def _touch_conversation(self, cid: str, first_question: str) -> None:
        with self.session_factory() as db:
            conv = db.get(Conversation, cid)
            if conv is None:
                title = " ".join(first_question.split())[:80] or "New conversation"
                db.add(Conversation(id=cid, title=title, created_at=utcnow(), updated_at=utcnow()))
            else:
                conv.updated_at = utcnow()
            db.commit()

    def list_conversations(self) -> list[ConversationSummary]:
        with self.session_factory() as db:
            rows = db.scalars(select(Conversation).order_by(Conversation.updated_at.desc())).all()
            return [ConversationSummary(id=r.id, title=r.title, created_at=r.created_at, updated_at=r.updated_at) for r in rows]

    def get_conversation(self, conversation_id: str) -> ConversationDetail:
        with self.session_factory() as db:
            conv = db.get(Conversation, conversation_id)
            if conv is None:
                raise NotFoundError("Conversation not found.", details={"conversation_id": conversation_id})
            summary = ConversationSummary(id=conv.id, title=conv.title, created_at=conv.created_at, updated_at=conv.updated_at)
        state = self.graph.get_state(self._config(conversation_id)).values or {}
        messages: list[StoredMessage] = []
        for m in state.get("messages", []):
            if m.type == "human":
                messages.append(StoredMessage(role="user", content=str(m.content)))
            else:
                extra = m.additional_kwargs or {}
                messages.append(StoredMessage(
                    role="assistant", content=str(m.content),
                    citations=[Citation(**c) for c in extra.get("citations", [])],
                    answer_origin=extra.get("answer_origin"), retrieval_path=extra.get("retrieval_path", []),
                    web_search_used=extra.get("web_search_used", False), limitations=extra.get("limitations"),
                ))
        return ConversationDetail(conversation=summary, messages=messages)

    def delete_conversation(self, conversation_id: str) -> None:
        with self.session_factory() as db:
            conv = db.get(Conversation, conversation_id)
            if conv is None:
                raise NotFoundError("Conversation not found.", details={"conversation_id": conversation_id})
            db.delete(conv)
            db.commit()
        self.checkpointer.delete_thread(conversation_id)
        self._locks.pop(conversation_id, None)
