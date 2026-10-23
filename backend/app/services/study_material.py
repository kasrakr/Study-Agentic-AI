"""Select source passages for quiz and flashcard generation."""

from __future__ import annotations

from dataclasses import dataclass

from app.errors import AppError
from app.rag.indexer import VectorIndex
from app.rag.retriever import retrieve_passages


@dataclass(frozen=True)
class Passage:
    number: int  # 1-based; the model refers to passages by this number
    text: str
    document_id: str
    filename: str
    page_number: int | None
    chunk_id: str


def collect_passages(
    index: VectorIndex, document_ids: list[str], *, limit: int, topic: str | None = None
) -> list[Passage]:
    """Pick up to `limit` passages from the selected documents.

    With a topic: the most similar passages. Without: an even spread across the
    whole of the selected material (not just the start of the first document).
    """
    if topic and topic.strip():
        found = retrieve_passages(index, topic.strip(), top_k=limit, document_ids=document_ids)
        rows = [(c.text, {"document_id": c.document_id, "filename": c.filename,
                          "page_number": c.page_number, "chunk_id": c.chunk_id}) for c in found]
    else:
        everything = index.list_chunks(document_ids)
        if len(everything) > limit:
            everything = [everything[int(i * len(everything) / limit)] for i in range(limit)]
        rows = everything
    if not rows:
        raise AppError(
            "No study material was found in the selected documents.",
            status_code=422, code="no_material", details={"document_ids": document_ids},
        )
    return [
        Passage(number=n, text=text, document_id=str(meta["document_id"]), filename=str(meta["filename"]),
                page_number=int(meta["page_number"]) if meta.get("page_number") is not None else None,
                chunk_id=str(meta["chunk_id"]))
        for n, (text, meta) in enumerate(rows, start=1)
    ]
