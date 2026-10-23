from __future__ import annotations

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.config import Settings
from app.dependencies import get_app_settings, get_document_service
from app.errors import AppError
from app.schemas.common import ErrorResponse
from app.schemas.documents import (
    DeleteResponse,
    DocumentListResponse,
    DocumentOut,
    UploadResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["documents"])

_ERRORS = {
    404: {"model": ErrorResponse}, 409: {"model": ErrorResponse},
    413: {"model": ErrorResponse}, 415: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post("/upload", response_model=UploadResponse, status_code=201, responses=_ERRORS)
def upload_document(
    response: Response,
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
    settings: Settings = Depends(get_app_settings),
) -> UploadResponse:
    """Upload and index a PDF, TXT or Markdown file.

    Indexing happens within the request. Returns 201 for a new document and 200
    with `duplicate: true` if identical content is already indexed.
    """
    # Read at most limit+1 bytes so an oversized upload is rejected without
    # loading all of it into memory.
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise AppError(
            f"File is larger than the {settings.max_upload_size_mb} MB limit.",
            status_code=413, code="file_too_large",
        )
    document, duplicate = service.ingest(file.filename or "untitled", data)
    if duplicate:
        response.status_code = 200
    return UploadResponse(document=DocumentOut.model_validate(document), duplicate=duplicate)


@router.get("", response_model=DocumentListResponse)
def list_documents(service: DocumentService = Depends(get_document_service)) -> DocumentListResponse:
    docs = service.list_documents()
    return DocumentListResponse(
        documents=[DocumentOut.model_validate(d) for d in docs], total=len(docs)
    )


@router.get("/{document_id}", response_model=DocumentOut, responses=_ERRORS)
def get_document(
    document_id: str, service: DocumentService = Depends(get_document_service)
) -> DocumentOut:
    return DocumentOut.model_validate(service.get_document(document_id))


@router.delete("/{document_id}", response_model=DeleteResponse, responses=_ERRORS)
def delete_document(
    document_id: str, service: DocumentService = Depends(get_document_service)
) -> DeleteResponse:
    """Removes the document's vectors, stored file and metadata."""
    service.delete_document(document_id)
    return DeleteResponse(id=document_id, deleted=True)
