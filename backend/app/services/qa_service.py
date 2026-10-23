"""Phase 3: simple document-only grounded question answering.

Flow: retrieve_documents -> generate_answer. Phase 4 replaces this with the
LangGraph workflow (evidence grading + Tavily fallback); the citation-building
logic here is written so it can be reused by the graph's answer node.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.prompts import GROUNDED_ANSWER_HUMAN, GROUNDED_ANSWER_SYSTEM, format_sources
from app.config import Settings
from app.errors import AppError
from app.rag.indexer import VectorIndex
from app.rag.retriever import RetrievedChunk, retrieve_passages
from app.resilience import call_openai
from app.schemas.chat import ChatResponse, Citation

logger = logging.getLogger(__name__)

SNIPPET_CHARS = 300
_MARKER = re.compile(r"\[(\d+)\]")

NO_DOCUMENTS_ANSWER = (
    "I couldn't find anything relevant in your uploaded documents. "
    "Upload study material that covers this topic, or check that the right documents are selected."
)


class GroundedAnswer(BaseModel):
    """Structured model output. All fields are required so the schema works with
    OpenAI strict structured outputs."""

    answer_found: bool = Field(description="True if the passages answer the question, fully or partly.")
    answer: str = Field(description="Markdown answer with [n] source markers.")
    cited_sources: list[int] = Field(description="Source numbers relied on.")
    limitations: str | None = Field(description="What is missing or uncertain, or null.")


def build_citations(
    chunks: list[RetrievedChunk], cited_numbers: list[int], answer_text: str
) -> tuple[list[Citation], str]:
    """Turn model-reported source numbers into citations built from real metadata.

    Invalid numbers are dropped and invalid [n] markers are stripped from the
    text, so the answer can never point at a source that doesn't exist.
    """
    valid = range(1, len(chunks) + 1)
    in_text = [int(m) for m in _MARKER.findall(answer_text)]
    ordered = [n for n in dict.fromkeys([*cited_numbers, *in_text]) if n in valid]

    def _keep_valid(match: re.Match[str]) -> str:
        return match.group(0) if int(match.group(1)) in valid else ""

    cleaned = _MARKER.sub(_keep_valid, answer_text)
    citations = []
    for number in ordered:
        chunk = chunks[number - 1]
        snippet = chunk.text if len(chunk.text) <= SNIPPET_CHARS else chunk.text[:SNIPPET_CHARS].rstrip() + "…"
        citations.append(
            Citation(
                source_number=number, document_id=chunk.document_id, filename=chunk.filename,
                page_number=chunk.page_number, chunk_id=chunk.chunk_id,
                snippet=snippet, score=chunk.score,
            )
        )
    return citations, cleaned


def answer_from_documents(
    *,
    question: str,
    index: VectorIndex,
    chat_model: BaseChatModel,
    settings: Settings,
    document_ids: list[str] | None = None,
    conversation_id: str | None = None,
) -> ChatResponse:
    started = time.perf_counter()
    conversation_id = conversation_id or uuid.uuid4().hex
    path = ["retrieve_documents"]

    chunks = retrieve_passages(
        index, question, top_k=settings.retrieval_top_k,
        document_ids=document_ids, min_score=settings.retrieval_min_score,
    )
    logger.info("Retrieved %d passages (conversation=%s)", len(chunks), conversation_id)

    if not chunks:  # nothing to ground an answer on, so don't call the LLM
        return ChatResponse(
            conversation_id=conversation_id, answer=NO_DOCUMENTS_ANSWER, citations=[],
            retrieval_path=path, evidence_found=False,
            limitations="No relevant passages were retrieved from the uploaded documents.",
            retrieved_count=0, latency_ms=_elapsed_ms(started),
        )

    messages = [
        SystemMessage(content=GROUNDED_ANSWER_SYSTEM),
        HumanMessage(content=GROUNDED_ANSWER_HUMAN.format(question=question, sources=format_sources(chunks))),
    ]
    structured = chat_model.with_structured_output(GroundedAnswer)
    try:
        result = call_openai(lambda: structured.invoke(messages), max_retries=settings.openai_max_retries)
    except AppError:
        raise
    except Exception as exc:
        logger.exception("Answer generation failed")
        raise AppError(
            "The model returned an unusable response. Please try again.",
            status_code=502, code="invalid_model_output",
        ) from exc
    path.append("generate_answer")

    if not isinstance(result, GroundedAnswer):
        raise AppError(
            "The model returned an unusable response. Please try again.",
            status_code=502, code="invalid_model_output",
        )

    if not result.answer_found:
        return ChatResponse(
            conversation_id=conversation_id, answer=result.answer.strip() or NO_DOCUMENTS_ANSWER,
            citations=[], retrieval_path=path, evidence_found=False,
            limitations=result.limitations or "The uploaded documents do not cover this question.",
            retrieved_count=len(chunks), latency_ms=_elapsed_ms(started),
        )

    citations, answer_text = build_citations(chunks, result.cited_sources, result.answer)
    limitations = result.limitations
    if not citations:
        note = "The answer did not cite any specific passage, so it could not be verified against the documents."
        limitations = f"{limitations} {note}" if limitations else note
    return ChatResponse(
        conversation_id=conversation_id, answer=answer_text.strip(), citations=citations,
        retrieval_path=path, evidence_found=bool(citations), limitations=limitations,
        retrieved_count=len(chunks), latency_ms=_elapsed_ms(started),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
