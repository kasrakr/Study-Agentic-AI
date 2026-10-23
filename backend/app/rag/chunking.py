"""Chunking. Each page is split on its own so page numbers stay exact.

Trade-off: a sentence that straddles a page break ends up in two chunks rather
than one spanning chunk. Exact citations matter more here than that edge case.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.loader import PageText


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    metadata: dict[str, str | int]


def build_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def chunk_pages(
    pages: list[PageText],
    *,
    document_id: str,
    filename: str,
    uploaded_at: datetime,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """Return chunks with deterministic ids: `<document_id>-p<page>-c<n>`.

    Deterministic ids make re-indexing idempotent. `page_number` is omitted from
    metadata (not set to None) for formats without pages, because Chroma does
    not accept None metadata values.
    """
    splitter = build_splitter(chunk_size, chunk_overlap)
    chunks: list[Chunk] = []
    running_index = 0
    for page in pages:
        for piece in splitter.split_text(page.text):
            piece = piece.strip()
            if not piece:
                continue
            page_tag = f"p{page.page_number}" if page.page_number is not None else "p0"
            chunk_id = f"{document_id}-{page_tag}-c{running_index}"
            metadata: dict[str, str | int] = {
                "document_id": document_id,
                "filename": filename,
                "chunk_id": chunk_id,
                "chunk_index": running_index,
                "uploaded_at": uploaded_at.isoformat(),
            }
            if page.page_number is not None:
                metadata["page_number"] = page.page_number
            chunks.append(Chunk(chunk_id=chunk_id, text=piece, metadata=metadata))
            running_index += 1
    return chunks
