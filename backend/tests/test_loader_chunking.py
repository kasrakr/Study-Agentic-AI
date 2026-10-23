from datetime import datetime, timezone

import pytest

from app.rag.chunking import chunk_pages
from app.rag.loader import DocumentLoadError, EmptyDocumentError, load_document
from tests.conftest import make_pdf


def test_pdf_extraction_preserves_page_numbers(tmp_path):
    path = tmp_path / "a.pdf"
    path.write_bytes(make_pdf(["Page one about cells.", "", "Page three about atoms."]))
    loaded = load_document(path, "pdf", max_pages=10)
    assert loaded.page_count == 3
    assert [(p.page_number, "cells" in p.text) for p in loaded.pages] == [(1, True), (3, False)]
    assert "atoms" in loaded.pages[1].text  # blank page 2 skipped, numbering intact


def test_pdf_without_text_is_rejected_as_empty(tmp_path):
    path = tmp_path / "blank.pdf"
    path.write_bytes(make_pdf(["", ""]))
    with pytest.raises(EmptyDocumentError, match="scanned"):
        load_document(path, "pdf", max_pages=10)


def test_malformed_pdf_is_rejected(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.7\nthis is not really a pdf")
    with pytest.raises(DocumentLoadError):
        load_document(path, "pdf", max_pages=10)


def test_page_limit_enforced(tmp_path):
    path = tmp_path / "long.pdf"
    path.write_bytes(make_pdf(["x"] * 3))
    with pytest.raises(DocumentLoadError, match="limit"):
        load_document(path, "pdf", max_pages=2)


def test_text_and_markdown_have_no_page_numbers(tmp_path):
    path = tmp_path / "n.md"
    path.write_text("# Title\n\nBody text.", encoding="utf-8")
    loaded = load_document(path, "md", max_pages=10)
    assert loaded.pages[0].page_number is None and loaded.page_count is None


def test_binary_and_non_utf8_text_rejected(tmp_path):
    (tmp_path / "b.txt").write_bytes(b"abc\x00def")
    (tmp_path / "l.txt").write_bytes("café".encode("latin-1"))
    with pytest.raises(DocumentLoadError):
        load_document(tmp_path / "b.txt", "txt", max_pages=10)
    with pytest.raises(DocumentLoadError, match="UTF-8"):
        load_document(tmp_path / "l.txt", "txt", max_pages=10)


def test_chunks_carry_metadata_and_stable_ids(tmp_path):
    path = tmp_path / "a.pdf"
    path.write_bytes(make_pdf(["Alpha sentence. " * 60, "Beta sentence. " * 60]))
    pages = load_document(path, "pdf", max_pages=10).pages
    kwargs = dict(document_id="doc_x", filename="a.pdf",
                  uploaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc), chunk_size=300, chunk_overlap=50)
    chunks = chunk_pages(pages, **kwargs)
    assert len(chunks) > 2
    assert all(len(c.text) <= 300 for c in chunks)
    assert {c.metadata["page_number"] for c in chunks} == {1, 2}
    assert all(c.metadata["document_id"] == "doc_x" and c.metadata["chunk_id"] == c.chunk_id for c in chunks)
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert [c.chunk_id for c in chunk_pages(pages, **kwargs)] == [c.chunk_id for c in chunks]  # deterministic
