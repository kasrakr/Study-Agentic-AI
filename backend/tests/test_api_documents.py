import openai
import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import FakeChatModel, FakeEmbeddings, TEST_KEY, make_pdf


def upload(client, name, data, content_type="application/octet-stream"):
    return client.post("/api/documents/upload", files={"file": (name, data, content_type)})


def vectors(client, doc_id):
    return client.app.state.vector_index.count_for_document(doc_id)


def test_health_reports_status_without_secrets(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["openai_configured"] is True
    assert TEST_KEY not in str(body)


def test_openai_health_uses_both_models(client, embeddings, chat_model):
    body = client.get("/api/health/openai").json()
    assert body["ok"] is True and embeddings.calls == 1 and chat_model.calls == 1


def test_upload_pdf_indexes_and_lists_document(client, settings):
    res = upload(client, "Lecture 1.pdf", make_pdf(["Cells divide by mitosis. " * 30, "Page two text. " * 30]))
    assert res.status_code == 201
    doc = res.json()["document"]
    assert res.json()["duplicate"] is False
    assert doc["status"] == "indexed" and doc["page_count"] == 2 and doc["chunk_count"] >= 2
    assert doc["id"].startswith("doc_") and doc["filename"] == "Lecture 1.pdf"
    assert doc["embedding_model"] == settings.openai_embedding_model
    assert vectors(client, doc["id"]) == doc["chunk_count"]
    assert (settings.upload_path / f"{doc['id']}.pdf").exists()

    listing = client.get("/api/documents").json()
    assert listing["total"] == 1 and listing["documents"][0]["id"] == doc["id"]
    assert client.get(f"/api/documents/{doc['id']}").json()["filename"] == "Lecture 1.pdf"


def test_duplicate_upload_does_not_reindex(client, embeddings):
    data = make_pdf(["Same content."])
    first = upload(client, "a.pdf", data).json()["document"]
    calls = embeddings.calls
    res = upload(client, "renamed.pdf", data)
    assert res.status_code == 200 and res.json()["duplicate"] is True
    assert res.json()["document"]["id"] == first["id"] and embeddings.calls == calls
    assert client.get("/api/documents").json()["total"] == 1


def test_text_and_markdown_uploads(client):
    assert upload(client, "notes.txt", b"Plain notes about entropy.").status_code == 201
    res = upload(client, "readme.md", b"# Heading\n\nMarkdown body.")
    assert res.status_code == 201 and res.json()["document"]["file_type"] == "md"


def test_unsupported_type_rejected(client):
    res = upload(client, "malware.exe", b"MZ...")
    assert res.status_code == 415 and res.json()["error"]["code"] == "unsupported_file_type"
    assert client.get("/api/documents").json()["total"] == 0


def test_oversized_upload_rejected(client):
    res = upload(client, "big.txt", b"a" * (1024 * 1024 + 10))  # limit is 1 MB in tests
    assert res.status_code == 413 and res.json()["error"]["code"] == "file_too_large"


def test_empty_file_and_fake_pdf_rejected(client):
    assert upload(client, "e.txt", b"").json()["error"]["code"] == "empty_file"
    res = upload(client, "fake.pdf", b"this is not a pdf")
    assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_pdf"


def test_scanned_pdf_is_recorded_as_failed_not_indexed(client, settings):
    res = upload(client, "scan.pdf", make_pdf(["", ""]))
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "document_unreadable" and "scanned" in err["message"]
    doc = client.get(f"/api/documents/{err['details']['document_id']}").json()
    assert doc["status"] == "failed" and doc["error_message"] and doc["chunk_count"] == 0
    assert vectors(client, doc["id"]) == 0
    assert not list(settings.upload_path.glob("*"))  # stored file cleaned up


def test_failed_upload_can_be_retried(client):
    data = b"Some real text to index."
    emb = client.app.state.embeddings
    emb.fail_with = RuntimeError("embedding backend down")
    assert upload(client, "n.txt", data).status_code == 500
    emb.fail_with = None
    res = upload(client, "n.txt", data)
    assert res.status_code == 201 and res.json()["document"]["status"] == "indexed"
    assert client.get("/api/documents").json()["total"] == 1


def test_openai_failure_during_indexing_is_sanitized_and_not_retried(client):
    emb = client.app.state.embeddings
    emb.fail_with = openai.AuthenticationError(
        "Incorrect API key: sk-leakedsecret123", body=None,
        response=httpx.Response(401, request=httpx.Request("POST", "https://x")),
    )
    res = upload(client, "n.txt", b"Text that will fail to embed.")
    assert res.status_code == 502 and res.json()["error"]["code"] == "openai_auth_failed"
    assert "leakedsecret" not in res.text
    assert emb.calls == 1  # no pointless retries on an unrecoverable error
    assert client.get("/api/documents").json()["documents"][0]["status"] == "failed"


def test_delete_removes_vectors_file_and_metadata(client, settings):
    keep = upload(client, "keep.txt", b"Keep this document about physics.").json()["document"]
    gone = upload(client, "gone.pdf", make_pdf(["Delete this about chemistry. " * 20])).json()["document"]
    assert vectors(client, gone["id"]) > 0

    res = client.delete(f"/api/documents/{gone['id']}")
    assert res.status_code == 200 and res.json() == {"id": gone["id"], "deleted": True}
    assert vectors(client, gone["id"]) == 0 and vectors(client, keep["id"]) > 0
    assert not (settings.upload_path / f"{gone['id']}.pdf").exists()
    assert client.get(f"/api/documents/{gone['id']}").status_code == 404
    assert [d["id"] for d in client.get("/api/documents").json()["documents"]] == [keep["id"]]


def test_unknown_document_returns_consistent_404(client):
    for res in (client.get("/api/documents/doc_nope"), client.delete("/api/documents/doc_nope")):
        assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"


def test_unsafe_filenames_are_sanitized_and_never_used_for_storage(client, settings):
    res = upload(client, "../../etc/pass<wd>.txt", b"harmless text content")
    doc = res.json()["document"]
    assert res.status_code == 201 and "/" not in doc["filename"] and "<" not in doc["filename"]
    assert [p.name for p in settings.upload_path.iterdir()] == [f"{doc['id']}.txt"]


def test_unhandled_errors_return_generic_500(settings):
    app = create_app(settings, embeddings=FakeEmbeddings(), chat_model=FakeChatModel())

    @app.get("/boom")
    def boom():
        raise RuntimeError(f"internal detail {TEST_KEY}")

    with TestClient(app, raise_server_exceptions=False) as c:
        res = c.get("/boom")
    assert res.status_code == 500 and res.json()["error"]["code"] == "internal_error"
    assert "internal detail" not in res.text and TEST_KEY not in res.text


def test_interrupted_processing_documents_are_marked_failed_on_startup(settings):
    from app.db.models import STATUS_PROCESSING, Document
    with TestClient(create_app(settings, embeddings=FakeEmbeddings(), chat_model=FakeChatModel())) as c:
        with c.app.state.session_factory() as s:
            s.add(Document(id="doc_stuck", filename="x.txt", file_type="txt", size_bytes=1,
                           sha256="0" * 64, stored_filename="doc_stuck.txt", status=STATUS_PROCESSING))
            s.commit()
    with TestClient(create_app(settings, embeddings=FakeEmbeddings(), chat_model=FakeChatModel())) as c:
        assert c.get("/api/documents/doc_stuck").json()["status"] == "failed"


def test_app_refuses_to_start_without_api_key(settings):
    import pytest
    from app.config import ConfigurationError
    bad = settings.model_copy(update={"openai_api_key": None})
    with pytest.raises(ConfigurationError):
        with TestClient(create_app(bad, embeddings=FakeEmbeddings(), chat_model=FakeChatModel())):
            pass
