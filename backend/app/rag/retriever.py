"""Retrieval: returns passages with their original document metadata."""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.indexer import VectorIndex


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    filename: str
    page_number: int | None
    text: str
    score: float  # cosine similarity; a relevance *signal*, not proof of an answer


def retrieve_passages(
    index: VectorIndex,
    query: str,
    *,
    top_k: int,
    document_ids: list[str] | None = None,
    min_score: float = 0.0,
) -> list[RetrievedChunk]:
    """Vector search over the uploaded documents.

    Similarity alone cannot decide whether the documents really answer a
    question; Phase 4 adds an LLM evidence-grading step on top of these results.
    """
    rows = index.search(query, k=top_k, document_ids=document_ids)
    chunks: list[RetrievedChunk] = []
    for text, meta, score in rows:
        if score < min_score:
            continue
        page = meta.get("page_number")
        chunks.append(
            RetrievedChunk(
                chunk_id=str(meta.get("chunk_id", "")),
                document_id=str(meta.get("document_id", "")),
                filename=str(meta.get("filename", "unknown")),
                page_number=int(page) if page is not None else None,
                text=text,
                score=round(score, 4),
            )
        )
    return chunks
