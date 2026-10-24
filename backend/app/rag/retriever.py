"""Retrieval: returns passages with their original document metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.rag.indexer import VectorIndex
from app.rag.lexical import reciprocal_rank_fusion


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    filename: str
    page_number: int | None
    text: str
    score: float  # cosine similarity; a relevance *signal*, not proof of an answer


def _to_chunk(text: str, meta: dict, score: float) -> RetrievedChunk:
    page = meta.get("page_number")
    return RetrievedChunk(
        chunk_id=str(meta.get("chunk_id", "")), document_id=str(meta.get("document_id", "")),
        filename=str(meta.get("filename", "unknown")), page_number=int(page) if page is not None else None,
        text=text, score=round(score, 4),
    )


def retrieve_passages(
    index: VectorIndex,
    query: str,
    *,
    top_k: int,
    document_ids: list[str] | None = None,
    min_score: float = 0.0,
    mode: Literal["vector", "hybrid"] = "vector",
) -> list[RetrievedChunk]:
    """Search the uploaded documents.

    `score` is always the cosine similarity between query and passage: a relevance *signal*, not proof
    that the passage answers the question (the LLM evidence grader decides that).

    mode="hybrid" fuses vector and BM25 keyword rankings (reciprocal-rank fusion). Keyword matches are
    kept even if their cosine similarity is under `min_score`, since exact-term hits are the point.
    """
    if mode == "hybrid":
        return _hybrid(index, query, top_k=top_k, document_ids=document_ids, min_score=min_score)
    rows = index.search(query, k=top_k, document_ids=document_ids)
    return [_to_chunk(t, m, s) for t, m, s in rows if s >= min_score]


def _hybrid(index: VectorIndex, query: str, *, top_k: int, document_ids: list[str] | None,
            min_score: float) -> list[RetrievedChunk]:
    pool = top_k * 3
    vector_rows = index.search(query, k=pool, document_ids=document_ids)
    lexical_rows = index.lexical_search(query, k=pool, document_ids=document_ids)

    by_id: dict[str, tuple[str, dict]] = {}
    cosine: dict[str, float] = {}
    for text, meta, score in vector_rows:
        by_id[meta["chunk_id"]] = (text, meta)
        cosine[meta["chunk_id"]] = score
    for text, meta, _ in lexical_rows:
        by_id.setdefault(meta["chunk_id"], (text, meta))

    fused = reciprocal_rank_fusion([[m["chunk_id"] for _, m, _ in vector_rows],
                                    [m["chunk_id"] for _, m, _ in lexical_rows]])
    lexical_ids = {m["chunk_id"] for _, m, _ in lexical_rows}
    ranked = sorted(fused, key=lambda cid: fused[cid], reverse=True)

    keep = [cid for cid in ranked if cid in lexical_ids or cosine.get(cid, 0.0) >= min_score][:top_k]
    missing = [cid for cid in keep if cid not in cosine]
    cosine.update(index.similarity(query, missing))  # keyword-only hits still get a cosine score
    return [_to_chunk(*by_id[cid], cosine.get(cid, 0.0)) for cid in keep]
