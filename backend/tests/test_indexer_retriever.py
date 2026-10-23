from datetime import datetime, timezone

import pytest

from app.rag.chunking import chunk_pages
from app.rag.indexer import EmbeddingModelMismatchError, VectorIndex
from app.rag.loader import PageText
from app.rag.retriever import retrieve_passages


def make_index(tmp_path, embeddings, model="embed-v1"):
    return VectorIndex(embeddings=embeddings, persist_directory=tmp_path / "vs",
                       collection_name="test_collection", embedding_model_name=model, retry_base_delay=0)


def chunks_for(doc_id: str, filename: str, pages: list[PageText]):
    return chunk_pages(pages, document_id=doc_id, filename=filename,
                       uploaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                       chunk_size=300, chunk_overlap=50)


@pytest.fixture
def populated(tmp_path, embeddings):
    index = make_index(tmp_path, embeddings)
    index.add_chunks(chunks_for("doc_bio", "bio.pdf", [
        PageText(1, "Mitochondria produce ATP through cellular respiration."),
        PageText(2, "Ribosomes translate messenger RNA into proteins."),
    ]))
    index.add_chunks(chunks_for("doc_phy", "phys.pdf", [
        PageText(1, "Newton's second law states that force equals mass times acceleration."),
    ]))
    return index


def test_retrieval_returns_most_relevant_passage_with_metadata(populated):
    top = retrieve_passages(populated, "what do ribosomes translate", top_k=3)[0]
    assert (top.filename, top.page_number, top.document_id) == ("bio.pdf", 2, "doc_bio")
    assert "Ribosomes" in top.text and top.chunk_id.startswith("doc_bio-p2")
    assert 0 < top.score <= 1


def test_retrieval_can_be_restricted_to_selected_documents(populated):
    hits = retrieve_passages(populated, "force mass acceleration", top_k=5, document_ids=["doc_bio"])
    assert hits and {h.document_id for h in hits} == {"doc_bio"}
    both = retrieve_passages(populated, "force mass", top_k=5, document_ids=["doc_bio", "doc_phy"])
    assert {h.document_id for h in both} == {"doc_bio", "doc_phy"}


def test_min_score_filters_weak_matches(populated):
    assert retrieve_passages(populated, "quantum chromodynamics gluons", top_k=5, min_score=0.9) == []


def test_text_documents_have_no_page_number(tmp_path, embeddings):
    index = make_index(tmp_path, embeddings)
    index.add_chunks(chunks_for("doc_t", "n.txt", [PageText(None, "Entropy always increases.")]))
    assert retrieve_passages(index, "entropy", top_k=1)[0].page_number is None


def test_delete_removes_only_that_documents_vectors(populated):
    assert populated.count_for_document("doc_bio") == 2
    populated.delete_document("doc_bio")
    assert populated.count_for_document("doc_bio") == 0
    assert populated.count_for_document("doc_phy") == 1
    assert {h.document_id for h in retrieve_passages(populated, "ribosomes mass", top_k=5)} == {"doc_phy"}


def test_reindexing_same_chunks_is_idempotent(populated):
    populated.add_chunks(chunks_for("doc_phy", "phys.pdf", [
        PageText(1, "Newton's second law states that force equals mass times acceleration.")]))
    assert populated.count_for_document("doc_phy") == 1


def test_index_persists_across_instances(tmp_path, embeddings):
    make_index(tmp_path, embeddings).add_chunks(chunks_for("doc_p", "p.txt", [PageText(None, "Persistent text.")]))
    assert make_index(tmp_path, embeddings).count_for_document("doc_p") == 1


def test_changing_embedding_model_is_refused(tmp_path, embeddings):
    make_index(tmp_path, embeddings, model="embed-v1")
    with pytest.raises(EmbeddingModelMismatchError, match="rebuild"):
        make_index(tmp_path, embeddings, model="embed-v2")
