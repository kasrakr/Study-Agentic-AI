from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_type: Literal["pdf", "txt", "md"]
    size_bytes: int
    page_count: int | None
    chunk_count: int
    status: Literal["processing", "indexed", "failed"]
    error_message: str | None
    embedding_model: str | None
    uploaded_at: datetime
    indexed_at: datetime | None


class UploadResponse(BaseModel):
    document: DocumentOut
    # True when identical content was already indexed, so nothing was re-processed.
    duplicate: bool


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]
    total: int


class DeleteResponse(BaseModel):
    id: str
    deleted: bool
