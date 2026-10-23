"""Document ingestion, listing and deletion."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import (
    STATUS_FAILED,
    STATUS_INDEXED,
    STATUS_PROCESSING,
    Document,
    utcnow,
)
from app.errors import AppError, NotFoundError
from app.rag.chunking import chunk_pages
from app.rag.indexer import VectorIndex
from app.rag.loader import SUPPORTED_TYPES, DocumentLoadError, load_document

logger = logging.getLogger(__name__)

MAX_FILENAME_LENGTH = 200


def sanitize_filename(name: str) -> str:
    """Display-name only. Files are stored under an internal id, never this name."""
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", name).strip(" .")
    if len(name) > MAX_FILENAME_LENGTH:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: MAX_FILENAME_LENGTH - len(ext) - 1] + dot + ext) if dot else name[:MAX_FILENAME_LENGTH]
    return name or "untitled"


def detect_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_TYPES:
        raise AppError(
            "Unsupported file type. Upload a PDF, TXT or Markdown file.",
            status_code=415, code="unsupported_file_type",
            details={"allowed_extensions": sorted(SUPPORTED_TYPES)},
        )
    return SUPPORTED_TYPES[ext]


def _validate_bytes(file_type: str, data: bytes) -> None:
    if not data:
        raise AppError("The uploaded file is empty.", status_code=422, code="empty_file")
    if file_type == "pdf" and not data.lstrip()[:5] == b"%PDF-":
        raise AppError(
            "The file is not a valid PDF (missing PDF header).",
            status_code=422, code="invalid_pdf",
        )


class DocumentService:
    def __init__(self, db: Session, index: VectorIndex, settings: Settings) -> None:
        self.db = db
        self.index = index
        self.settings = settings

    # ---------- ingestion ----------
    def ingest(self, filename: str, data: bytes) -> tuple[Document, bool]:
        """Validate, extract, chunk, embed and persist. Returns (document, duplicate)."""
        display_name = sanitize_filename(filename)
        file_type = detect_file_type(display_name)
        if len(data) > self.settings.max_upload_bytes:
            raise AppError(
                f"File is larger than the {self.settings.max_upload_size_mb} MB limit.",
                status_code=413, code="file_too_large",
            )
        _validate_bytes(file_type, data)

        digest = hashlib.sha256(data).hexdigest()
        document_id = f"doc_{digest[:16]}"

        existing = self.db.get(Document, document_id)
        if existing is not None:
            if existing.status == STATUS_INDEXED:
                return existing, True
            if existing.status == STATUS_PROCESSING:
                raise AppError(
                    "This file is already being processed.",
                    status_code=409, code="already_processing",
                    details={"document_id": document_id},
                )
            # A previously failed upload: retry in place.
            doc = existing
            doc.filename, doc.file_type, doc.size_bytes = display_name, file_type, len(data)
            doc.status, doc.error_message, doc.uploaded_at = STATUS_PROCESSING, None, utcnow()
        else:
            doc = Document(
                id=document_id, filename=display_name, file_type=file_type,
                size_bytes=len(data), sha256=digest,
                stored_filename=f"{document_id}.{file_type}",
                status=STATUS_PROCESSING, uploaded_at=utcnow(),
            )
            self.db.add(doc)
        try:
            self.db.commit()
        except IntegrityError:  # concurrent upload of the same bytes
            self.db.rollback()
            raced = self.db.get(Document, document_id)
            if raced is not None and raced.status == STATUS_INDEXED:
                return raced, True
            raise AppError(
                "This file is already being processed.",
                status_code=409, code="already_processing",
                details={"document_id": document_id},
            )

        stored_path = self.settings.upload_path / doc.stored_filename
        try:
            self._process(doc, data, stored_path)
        except Exception as exc:
            self._cleanup_failed(doc, stored_path)
            app_error = self._as_app_error(exc, document_id)
            doc.status = STATUS_FAILED
            doc.error_message = app_error.message
            self.db.commit()
            raise app_error from exc
        return doc, False

    def _process(self, doc: Document, data: bytes, stored_path: Path) -> None:
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(data)

        loaded = load_document(stored_path, doc.file_type, max_pages=self.settings.max_document_pages)
        chunks = chunk_pages(
            loaded.pages,
            document_id=doc.id,
            filename=doc.filename,
            uploaded_at=doc.uploaded_at,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        if not chunks:
            raise DocumentLoadError("No text chunks could be produced from this file.")

        # Clear leftovers from an earlier failed attempt before re-adding.
        self.index.delete_document(doc.id)
        self.index.add_chunks(chunks, batch_size=self.settings.embedding_batch_size)

        stored = self.index.count_for_document(doc.id)
        if stored != len(chunks):
            raise RuntimeError(f"Index verification failed: expected {len(chunks)} chunks, found {stored}")

        doc.page_count = loaded.page_count
        doc.chunk_count = len(chunks)
        doc.embedding_model = self.index.embedding_model_name
        doc.status = STATUS_INDEXED
        doc.error_message = None
        doc.indexed_at = utcnow()
        self.db.commit()
        logger.info("Indexed %s (%s): %d chunks", doc.id, doc.file_type, len(chunks))

    def _cleanup_failed(self, doc: Document, stored_path: Path) -> None:
        """Best-effort removal of partial vectors and the stored file."""
        self.db.rollback()
        try:
            self.index.delete_document(doc.id)
        except Exception:
            logger.exception("Could not remove partial vectors for %s", doc.id)
        stored_path.unlink(missing_ok=True)

    @staticmethod
    def _as_app_error(exc: Exception, document_id: str) -> AppError:
        details = {"document_id": document_id}
        if isinstance(exc, AppError):  # e.g. sanitized OpenAI errors
            exc.details = {**exc.details, **details}
            return exc
        if isinstance(exc, DocumentLoadError):
            return AppError(str(exc), status_code=422, code="document_unreadable", details=details)
        logger.exception("Indexing failed for %s", document_id)
        return AppError(
            "Indexing failed because of an internal error. See the server log.",
            status_code=500, code="indexing_failed", details=details,
        )

    # ---------- queries ----------
    def list_documents(self) -> list[Document]:
        stmt = select(Document).order_by(Document.uploaded_at.desc())
        return list(self.db.scalars(stmt))

    def get_document(self, document_id: str) -> Document:
        doc = self.db.get(Document, document_id)
        if doc is None:
            raise NotFoundError("Document not found.", details={"document_id": document_id})
        return doc

    def require_indexed(self, document_ids: list[str]) -> None:
        """Validate that every id refers to an indexed document."""
        unique = list(dict.fromkeys(document_ids))
        rows = self.db.scalars(select(Document).where(Document.id.in_(unique))).all()
        by_id = {d.id: d for d in rows}
        missing = [i for i in unique if i not in by_id]
        not_ready = [i for i in unique if i in by_id and by_id[i].status != STATUS_INDEXED]
        if missing:
            raise NotFoundError("Some documents were not found.", details={"document_ids": missing})
        if not_ready:
            raise AppError(
                "Some documents are not indexed.", status_code=422,
                code="document_not_indexed", details={"document_ids": not_ready},
            )

    def count_indexed(self) -> int:
        return len(list(self.db.scalars(select(Document.id).where(Document.status == STATUS_INDEXED))))

    # ---------- deletion ----------
    def delete_document(self, document_id: str) -> None:
        doc = self.get_document(document_id)
        if doc.status == STATUS_PROCESSING:
            raise AppError("The document is still being processed.", status_code=409, code="processing")
        self.index.delete_document(document_id)  # vectors first; abort if this fails
        (self.settings.upload_path / doc.stored_filename).unlink(missing_ok=True)
        self.db.delete(doc)
        self.db.commit()

    def recover_interrupted(self) -> int:
        """Mark documents left in 'processing' by a crash as failed."""
        stuck = list(self.db.scalars(select(Document).where(Document.status == STATUS_PROCESSING)))
        for doc in stuck:
            doc.status = STATUS_FAILED
            doc.error_message = "Processing was interrupted. Delete and upload the file again."
        if stuck:
            self.db.commit()
        return len(stuck)
