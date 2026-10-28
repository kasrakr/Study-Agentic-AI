"""LangGraph nodes. Each node has one responsibility and returns a partial state update.

`@traced` wraps every node: it emits real start/finish events to the stream
(when streaming) and records a factual execution event in the state, so the UI
timeline reflects what actually ran. Nothing here exposes model reasoning.
"""

from __future__ import annotations

import functools
import logging
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from sqlalchemy import select

from app.agent import prompts
from app.agent.citations import build_citations
from app.agent.schemas import (
    DocumentGrade,
    IntentResult,
    MissingInfoPlan,
    RewrittenQuery,
    WebEvidenceGrade,
)
from app.agent.state import AgentState
from app.config import Settings
from app.rag.indexer import VectorIndex
from app.db.models import STATUS_INDEXED, Document
from app.rag.retriever import retrieve_passages
from app.resilience import invoke_structured, stream_text
from app.services.web_search import WebSearchError, WebSearchProvider

logger = logging.getLogger(__name__)

HISTORY_CHARS = 500
MAX_WEB_QUERY_CHARS = 300


@dataclass
class AgentDeps:
    settings: Settings
    index: VectorIndex
    chat_model: Any
    web_search: WebSearchProvider | None
    session_factory: Any  # sqlalchemy sessionmaker; used by study-tool nodes


def _writer() -> Callable[[dict], None]:
    try:
        return get_stream_writer()
    except Exception:  # outside a graph run (e.g. unit-testing a node directly)
        return lambda _payload: None


def traced(step: str):
    """Decorator for node methods. A node may return a private `_detail` string."""

    def decorator(fn):  # noqa: ANN001
        @functools.wraps(fn)
        def wrapper(self, state: AgentState) -> dict[str, Any]:
            write = _writer()
            write({"type": "status", "step": step, "phase": "started"})
            started = time.perf_counter()
            update = fn(self, state)
            detail = update.pop("_detail", None)
            ms = int((time.perf_counter() - started) * 1000)
            write({"type": "status", "step": step, "phase": "completed", "detail": detail, "duration_ms": ms})
            update["execution_events"] = [{"step": step, "detail": detail, "duration_ms": ms}]
            return update

        return wrapper

    return decorator


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


class AgentNodes:
    def __init__(self, deps: AgentDeps) -> None:
        self.d = deps
        self.s = deps.settings

    # ------------------------------------------------------------ helpers
    def _structured(self, schema, system: str, human: str):  # noqa: ANN001
        return invoke_structured(self.d.chat_model, schema, system, human, max_retries=self.s.openai_max_retries)

    def _history(self, state: AgentState) -> list[tuple[str, str]]:
        limit = self.s.agent_history_messages
        if limit == 0:
            return []
        out = []
        for m in (state.get("messages") or [])[-limit:]:
            role = "Student" if m.type == "human" else "Assistant"
            text = m.content if isinstance(m.content, str) else ""
            out.append((role, text[:HISTORY_CHARS]))
        return out

    @staticmethod
    def _turn_messages(state: AgentState, answer: str, extras: dict[str, Any], current_step: str) -> list:
        # The finishing node is still running, so add its own step to the path recorded so far.
        path = [e["step"] for e in state.get("execution_events") or []] + [current_step]
        return [HumanMessage(content=state["question"]),
                AIMessage(content=answer, additional_kwargs={**extras, "retrieval_path": path})]

    # ------------------------------------------------------------ nodes
    @traced("classify_intent")
    def classify_intent(self, state: AgentState) -> dict[str, Any]:
        result = self._structured(
            IntentResult, prompts.CLASSIFY_SYSTEM,
            prompts.CLASSIFY_HUMAN.format(history=prompts.format_history(self._history(state)), question=state["question"]),
        )
        standalone = (result.standalone_question or "").strip()[:1000] or state["question"]
        return {
            "intent": result.intent,
            "wants_web": result.wants_web,
            "study_tool_topic": (result.topic or "").strip()[:200] or None,
            "standalone_question": standalone,
            "retrieval_query": standalone,
            "_detail": f"intent: {result.intent}" + ("; external information requested" if result.wants_web else ""),
        }

    @traced("retrieve_documents")
    def retrieve_documents(self, state: AgentState) -> dict[str, Any]:
        found = retrieve_passages(
            self.d.index, state["retrieval_query"], top_k=self.s.retrieval_top_k,
            document_ids=state.get("selected_document_ids"), min_score=self.s.retrieval_min_score,
            mode=self.s.retrieval_mode,
        )
        new = [asdict(c) for c in found]
        # On a retry, keep earlier hits so a rewritten query can only add evidence.
        merged: dict[str, dict] = {c["chunk_id"]: c for c in state.get("retrieved_document_chunks") or []}
        for c in new:
            if c["chunk_id"] not in merged or c["score"] > merged[c["chunk_id"]]["score"]:
                merged[c["chunk_id"]] = c
        chunks = sorted(merged.values(), key=lambda c: c["score"], reverse=True)[: self.s.retrieval_top_k * 2]
        detail = (f"{len(new)} passages found; best similarity {max(c['score'] for c in new):.2f}"
                  if new else "no passages found")
        return {"retrieved_document_chunks": chunks, "_detail": detail}

    @traced("grade_document_evidence")
    def grade_document_evidence(self, state: AgentState) -> dict[str, Any]:
        chunks = state.get("retrieved_document_chunks") or []
        question = state["standalone_question"]
        if not chunks:  # nothing to grade; skip the LLM call
            return {
                "evidence_verdict": "insufficient", "evidence_sufficient": False,
                "evidence_reason": "No passages were retrieved from the uploaded documents.",
                "missing_information": [question], "document_sources": [],
                "retrieval_may_have_missed": False,
                "_detail": "insufficient: nothing retrieved",
            }
        top = max(c["score"] for c in chunks)
        weak = top < self.s.retrieval_weak_score
        signals = f"{len(chunks)} passages; top cosine similarity {top:.2f}" + (" (weak)" if weak else "")
        grade = self._structured(
            DocumentGrade, prompts.GRADE_DOCS_SYSTEM,
            prompts.GRADE_DOCS_HUMAN.format(question=question, signals=signals, passages=prompts.format_passages(chunks)),
        )
        relevant = [i for i in dict.fromkeys(grade.relevant_passages) if 1 <= i <= len(chunks)]
        if relevant:
            selected = [chunks[i - 1] for i in relevant]
        elif grade.verdict != "insufficient":
            selected = chunks
        else:
            selected = []
        sources = [{**c, "marker": f"D{n}"} for n, c in enumerate(selected, start=1)]
        missing = [m.strip() for m in grade.missing_information if m.strip()][:5]
        if grade.verdict != "sufficient" and not missing:
            missing = [question]
        return {
            "evidence_verdict": grade.verdict,
            "evidence_sufficient": grade.verdict == "sufficient",
            "evidence_reason": grade.reason.strip(),
            "missing_information": missing if grade.verdict != "sufficient" else [],
            "document_sources": sources,
            # The similarity signals went to the grader as hints; the grader decides whether a
            # rewrite could help. (A weak score alone also describes a topic the documents simply
            # don't cover, where a rewrite would only waste a call.)
            "retrieval_may_have_missed": grade.retrieval_may_have_missed and grade.verdict != "sufficient",
            "_detail": f"{grade.verdict} ({len(sources)} relevant passages; {signals})",
        }

    @traced("rewrite_query")
    def rewrite_query(self, state: AgentState) -> dict[str, Any]:
        previous = state["retrieval_query"]
        result = self._structured(
            RewrittenQuery, prompts.REWRITE_SYSTEM,
            prompts.REWRITE_HUMAN.format(question=state["standalone_question"], previous=previous,
                                         reason=state.get("evidence_reason") or "not specified"),
        )
        new = result.query.strip()[:MAX_WEB_QUERY_CHARS]
        changed = bool(new) and _norm(new) != _norm(previous)
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "retrieval_query": new if changed else previous,
            "query_changed": changed,
            "_detail": f'retrying search with: "{new}"' if changed else "no better query found",
        }

    @traced("identify_missing_information")
    def identify_missing_information(self, state: AgentState) -> dict[str, Any]:
        question = state["standalone_question"]
        missing = state.get("missing_information") or []
        no_evidence = not state.get("document_sources") and not state.get("retrieved_document_chunks")
        if no_evidence or self.d.web_search is None:
            # Nothing document-specific to narrow down (or no search will run): skip the LLM call.
            query = question[:MAX_WEB_QUERY_CHARS]
            return {"web_search_query": query, "missing_information": missing or [question],
                    "_detail": "web fallback required: documents have no relevant evidence"}
        plan = self._structured(
            MissingInfoPlan, prompts.IDENTIFY_SYSTEM,
            prompts.IDENTIFY_HUMAN.format(
                question=question, reason=state.get("evidence_reason") or "n/a",
                missing="; ".join(missing) or "none reported", wants_web=state.get("wants_web", False)),
        )
        query = plan.web_search_query.strip()[:MAX_WEB_QUERY_CHARS] or question[:MAX_WEB_QUERY_CHARS]
        cleaned = [m.strip() for m in plan.missing_information if m.strip()][:5] or missing
        why = "external information requested" if state.get("wants_web") else "documents only partly cover the question"
        return {"web_search_query": query, "missing_information": cleaned,
                "_detail": f"web fallback required: {why}"}

    @traced("web_search")
    def web_search(self, state: AgentState) -> dict[str, Any]:
        provider = self.d.web_search
        if provider is None:
            msg = "Web search is not configured (set TAVILY_API_KEY in backend/.env)."
            return {"web_search_results": [], "web_search_used": False, "web_search_error": msg,
                    "_detail": "skipped: not configured"}
        try:
            results = provider.search(state["web_search_query"], max_results=self.s.tavily_max_results)
        except WebSearchError as exc:
            logger.warning("Web search failed: %s", exc.code)
            return {"web_search_results": [], "web_search_used": True, "web_search_error": exc.message,
                    "_detail": f"failed: {exc.message}"}
        rows = [{"title": r.title, "url": r.url, "content": r.content, "score": r.score,
                 "published_date": r.published_date} for r in results]
        return {"web_search_results": rows, "web_search_used": True, "web_search_error": None,
                "_detail": f"{len(rows)} results" if rows else "no results"}

    @traced("grade_web_evidence")
    def grade_web_evidence(self, state: AgentState) -> dict[str, Any]:
        results = state.get("web_search_results") or []
        if not results:
            return {"web_sources": [], "web_coverage": "none", "_detail": "nothing to evaluate"}
        grade = self._structured(
            WebEvidenceGrade, prompts.GRADE_WEB_SYSTEM,
            prompts.GRADE_WEB_HUMAN.format(
                question=state["standalone_question"],
                missing="; ".join(state.get("missing_information") or []) or "the whole question",
                results=prompts.format_web_results(results)),
        )
        keep: list[int] = []
        for g in grade.results:
            if 1 <= g.index <= len(results) and g.relevant and g.reliability != "low" and g.index not in keep:
                keep.append(g.index)
        sources = [{**results[i - 1], "marker": f"W{n}"} for n, i in enumerate(keep, start=1)]
        coverage = "none" if not sources else (grade.coverage if grade.coverage != "none" else "partial")
        return {"web_sources": sources, "web_coverage": coverage,
                "_detail": f"{len(sources)} of {len(results)} results kept; coverage {coverage}"}

    def _evidence_notes(self, state: AgentState) -> str:
        notes = [f"Documents: {state.get('evidence_verdict')}. {state.get('evidence_reason', '')}".strip()]
        if state.get("missing_information"):
            notes.append("Not answered by the documents: " + "; ".join(state["missing_information"]))
        if state.get("web_search_used"):
            notes.append(f"Web search was used; relevant results kept: {len(state.get('web_sources') or [])}.")
        return " ".join(notes)

    def _limitations(self, state: AgentState, has_citations: bool) -> str | None:
        parts: list[str] = []
        web_sources = state.get("web_sources") or []
        if state.get("evidence_verdict") != "sufficient":
            covered_by_web = bool(web_sources) and state.get("web_coverage") == "full"
            if state.get("missing_information") and not covered_by_web:
                parts.append("Not found in the available sources: " + "; ".join(state["missing_information"]) + ".")
        if state.get("web_search_error"):
            parts.append(f"Web search did not help: {state['web_search_error']}")
        elif state.get("web_search_used") and not web_sources:
            parts.append("A web search found no relevant, reliable results.")
        elif web_sources and state.get("web_coverage") == "partial":
            parts.append("Web sources cover only part of what was missing.")
        if not has_citations:
            parts.append("No source could be cited, so this answer could not be verified.")
        return " ".join(parts) or None

    @traced("generate_answer")
    def generate_answer(self, state: AgentState) -> dict[str, Any]:
        docs = state.get("document_sources") or []
        web = state.get("web_sources") or []
        write = _writer()

        if not docs and not web:  # no evidence at all: don't ask the model to answer
            tail = " or from a web search." if state.get("web_search_used") else "."
            answer = "I couldn't verify an answer to this from your uploaded documents" + tail
            limitations = self._limitations(state, has_citations=False)
            write({"type": "token", "text": answer})
            return self._answer_update(state, answer, [], "none", limitations, detail="no evidence available; no answer generated")

        style = prompts.STYLE_SIMPLE if state.get("intent") == "explain_simply" else prompts.STYLE_STANDARD
        messages = [
            SystemMessage(content=prompts.ANSWER_SYSTEM.format(style=style)),
            HumanMessage(content=prompts.ANSWER_HUMAN.format(
                question=state["standalone_question"], notes=self._evidence_notes(state),
                sources=prompts.format_answer_sources(docs, web))),
        ]
        text = stream_text(
            self.d.chat_model, messages,
            on_token=lambda t: write({"type": "token", "text": t}), max_retries=self.s.openai_max_retries,
        )
        citations, cleaned, origin = build_citations(docs, web, text)
        limitations = self._limitations(state, has_citations=bool(citations))
        return self._answer_update(state, cleaned.strip(), citations, origin, limitations,
                                   detail=f"answer from {origin.replace('_', ' ')}; {len(citations)} citations")

    def _answer_update(self, state, answer, citations, origin, limitations, *, detail) -> dict[str, Any]:  # noqa: ANN001
        dumped = [c.model_dump() for c in citations]
        extras = {"citations": dumped, "answer_origin": origin, "limitations": limitations,
                  "web_search_used": state.get("web_search_used", False)}
        return {
            "final_answer": answer, "answer_sources": dumped, "answer_origin": origin,
            "limitations": limitations, "messages": self._turn_messages(state, answer, extras, "generate_answer"),
            "_detail": detail,
        }

    @traced("respond_smalltalk")
    def respond_smalltalk(self, state: AgentState) -> dict[str, Any]:
        # Use the language of the current question, without changing tool or API data.
        persian = any("\u0600" <= ch <= "\u06ff" for ch in state.get("question", ""))
        answer = prompts.SMALLTALK_REPLY_FA if persian else prompts.SMALLTALK_REPLY
        _writer()({"type": "token", "text": answer})
        return {"final_answer": answer, "answer_origin": "none", "answer_sources": [],
                "messages": self._turn_messages(state, answer, {"answer_origin": "none"}, "respond_smalltalk"),
                "_detail": "no document search needed"}

    # ------------------------------------------------------------ study tools
    def _tool_document_ids(self, state: AgentState) -> list[str]:
        """Selected documents, else the most recent indexed ones (quizzes never use the web)."""
        if state.get("selected_document_ids"):
            return state["selected_document_ids"]
        with self.d.session_factory() as db:
            return list(db.scalars(
                select(Document.id).where(Document.status == STATUS_INDEXED).order_by(Document.uploaded_at.desc()).limit(10)))

    def _tool_unavailable(self, state: AgentState, what: str, step: str) -> dict[str, Any]:
        answer = f"I need at least one indexed document to make {what}. Upload study material in the Library first."
        _writer()({"type": "token", "text": answer})
        return {"final_answer": answer, "answer_origin": "none", "answer_sources": [],
                "messages": self._turn_messages(state, answer, {"answer_origin": "none"}, step),
                "_detail": "no indexed documents"}

    def _tool_done(self, state: AgentState, answer: str, artifact: dict, detail: str, step: str) -> dict[str, Any]:
        _writer()({"type": "token", "text": answer})
        return {"final_answer": answer, "answer_origin": "documents", "answer_sources": [], "artifact": artifact,
                "messages": self._turn_messages(state, answer, {"answer_origin": "documents", "artifact": artifact}, step),
                "_detail": detail}

    @traced("generate_quiz")
    def generate_quiz(self, state: AgentState) -> dict[str, Any]:
        from app.services.quiz_service import QuizService

        ids = self._tool_document_ids(state)
        if not ids:
            return self._tool_unavailable(state, "a quiz", "generate_quiz")
        topic = state.get("study_tool_topic")
        with self.d.session_factory() as db:
            service = QuizService(db, self.d.index, self.d.chat_model, self.s)
            quiz = service.generate(document_ids=ids, question_count=5,
                                    question_types=["multiple_choice", "true_false"], difficulty="medium", topic=topic)
            count = service.get_quiz(quiz.id).question_count
        about = f" on {topic}" if topic else ""
        answer = (f"I made a {count}-question quiz{about} from your documents. "
                  "Open it on the Quiz page to answer it and see your score.")
        return self._tool_done(state, answer, {"type": "quiz", "id": quiz.id}, f"{count} questions from {len(ids)} document(s)", "generate_quiz")

    @traced("generate_flashcards")
    def generate_flashcards(self, state: AgentState) -> dict[str, Any]:
        from app.services.flashcard_service import FlashcardService

        ids = self._tool_document_ids(state)
        if not ids:
            return self._tool_unavailable(state, "flashcards", "generate_flashcards")
        topic = state.get("study_tool_topic")
        with self.d.session_factory() as db:
            service = FlashcardService(db, self.d.index, self.d.chat_model, self.s)
            deck = service.generate(document_ids=ids, card_count=10, topic=topic)
            count = len(service.to_out(deck).cards)
        about = f" on {topic}" if topic else ""
        answer = f"I made {count} flashcards{about} from your documents. Open them on the Flashcards page to review."
        return self._tool_done(state, answer, {"type": "flashcards", "id": deck.id}, f"{count} cards from {len(ids)} document(s)", "generate_flashcards")
