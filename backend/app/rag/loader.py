"""Text extraction with page numbers preserved where the format has pages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {".pdf": "pdf", ".txt": "txt", ".md": "md", ".markdown": "md"}


class DocumentLoadError(Exception):
    """The file could not be read (malformed, encrypted, wrong encoding...)."""


class EmptyDocumentError(DocumentLoadError):
    """The file was readable but contained no extractable text."""


@dataclass(frozen=True)
class PageText:
    page_number: int | None  # 1-based for PDFs; None for plain text
    text: str


@dataclass(frozen=True)
class LoadedDocument:
    pages: list[PageText]
    page_count: int | None  # total pages in the source (including blank ones)


def load_document(path: Path, file_type: str, *, max_pages: int) -> LoadedDocument:
    if file_type == "pdf":
        return _load_pdf(path, max_pages=max_pages)
    if file_type in ("txt", "md"):
        return _load_text(path)
    raise DocumentLoadError(f"Unsupported file type: {file_type}")


def _load_pdf(path: Path, *, max_pages: int) -> LoadedDocument:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # PyMuPDF raises several error types for bad files
        raise DocumentLoadError("The PDF is malformed or could not be opened.") from exc

    try:
        if doc.needs_pass:
            raise DocumentLoadError("The PDF is password-protected and cannot be read.")
        if doc.page_count > max_pages:
            raise DocumentLoadError(
                f"The PDF has {doc.page_count} pages; the limit is {max_pages} "
                "(MAX_DOCUMENT_PAGES)."
            )
        pages: list[PageText] = []
        for index in range(doc.page_count):
            try:
                text = doc[index].get_text("text")
            except Exception as exc:
                raise DocumentLoadError(f"Could not read page {index + 1}.") from exc
            text = _clean(text)
            if text:
                pages.append(PageText(page_number=index + 1, text=text))
        page_count = doc.page_count
    finally:
        doc.close()

    if not pages:
        raise EmptyDocumentError(
            "No extractable text was found. The PDF may be scanned images; "
            "OCR is not supported."
        )
    return LoadedDocument(pages=pages, page_count=page_count)


def _load_text(path: Path) -> LoadedDocument:
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise DocumentLoadError("The file looks binary, not text.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentLoadError("The text file is not valid UTF-8.") from exc
    text = _clean(text)
    if not text:
        raise EmptyDocumentError("The file contains no text.")
    return LoadedDocument(pages=[PageText(page_number=None, text=text)], page_count=None)


def _clean(text: str) -> str:
    return text.replace("\x00", "").strip()
