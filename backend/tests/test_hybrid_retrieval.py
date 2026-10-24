from datetime import datetime, timezone

import pytest

from app.rag.chunking import chunk_pages
from app.rag.indexer import VectorIndex
from app.rag.lexical import BM25, reciprocal_rank_fusion, tokenize
from app.rag.loader import PageText
from app.rag.retriever import retrieve_passages
from tests.conftest import make_pdf


def test_tokenizer_splits_identifiers_and_equations():
    assert tokenize("Code XJ-4471, E=mc2!") == ["code", "xj", "4471", "e", "mc2"]


def test_bm25_ranks_rare_terms_above_common_ones_and_skips_non_matches():
    docs = [tokenize(t) for t in ["the cat sat", "the dog sat", "the zyzzyva sat", "unrelated words"]]
    ranked = BM25(docs).top(tokenize("the zyzzyva"), k=5)
    assert ranked[0][0] == 2 and 3 not in [i for i, _ in ranked]


def test_rrf_rewards_agreement_between_lists():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["c", "a"]])
    assert fused["a"] > fused["c"] > fused["b"]
    assert fused["a"] == pytest.approx(1 / 61 + 1 / 62)


@pytest.fixture
def index(tmp_path, embeddings):
    idx = VectorIndex(embeddings=embeddings, persist_directory=tmp_path / "vs", collection_name="hybrid_test",
                      embedding_model_name="m", retry_base_delay=0)

    def add(doc, text):
        idx.add_chunks(chunk_pages([PageText(None, text)], document_id=doc, filename=f"{doc}.txt",
                                   uploaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc), chunk_size=500, chunk_overlap=0))

    add("target", "Error code XJ4471 indicates the compressor has overheated and must be reset.")
    add("d1", "What is the meaning of an error code in general and what should students do when they see any error code?")
    add("d2", "An error code is a number that tells the user what went wrong and what is the next step to take for the error code.")
    add("d3", "When any error code appears students should note what the error code is and what to do next about the error code.")
    add("d4", "The meaning of every error code is listed so students know what to do when an error code is shown.")
    add("d5", "Cooking pasta requires boiling water and salt.")
    add("d6", "The French revolution began in 1789 in Paris.")
    idx.add = add  # type: ignore[attr-defined]
    return idx


def ids(chunks):
    return [c.document_id for c in chunks]


def test_hybrid_surfaces_an_exact_identifier_that_vector_search_misses(index):
    q = "what does XJ4471 mean"
    assert "target" not in ids(retrieve_passages(index, q, top_k=2, mode="vector"))
    hybrid = retrieve_passages(index, q, top_k=2, mode="hybrid")
    assert "target" in ids(hybrid)
    assert all(c.score > 0 for c in hybrid)  # every result carries a cosine score, including keyword hits


def test_hybrid_matches_vector_when_vector_is_already_right(index):
    assert ids(retrieve_passages(index, "XJ4471", top_k=1, mode="hybrid")) == ids(retrieve_passages(index, "XJ4471", top_k=1))


def test_hybrid_respects_document_selection(index):
    hits = retrieve_passages(index, "what does XJ4471 mean", top_k=3, document_ids=["d1", "d2"], mode="hybrid")
    assert set(ids(hits)) <= {"d1", "d2"}


def test_min_score_filters_vector_hits_but_not_exact_keyword_hits(index):
    hits = retrieve_passages(index, "XJ4471", top_k=3, min_score=0.99, mode="hybrid")
    assert ids(hits) == ["target"]  # exact-term match kept; weak vector-only neighbours dropped


def test_keyword_only_hit_outside_the_vector_pool_gets_a_cosine_score(index):
    # top_k=1 -> vector pool of 3; the identifier chunk is lexical rank 1 but not necessarily in the vector pool.
    hits = retrieve_passages(index, "what does XJ4471 mean", top_k=3, mode="hybrid")
    target = next(c for c in hits if c.document_id == "target")
    direct = index.similarity("what does XJ4471 mean", [target.chunk_id])[target.chunk_id]
    assert target.score == pytest.approx(direct, abs=1e-3)


def test_keyword_index_is_rebuilt_after_deletes_and_adds(index):
    assert index.lexical_search("XJ4471", k=3)[0][1]["document_id"] == "target"
    index.delete_document("target")
    assert index.lexical_search("XJ4471", k=3) == []
    index.add("fresh", "Replacement note about XJ4471 coolant.")
    assert index.lexical_search("XJ4471", k=3)[0][1]["document_id"] == "fresh"


def test_retrieval_mode_is_validated(settings):
    with pytest.raises(ValueError):
        settings.model_copy(update={}).__class__(_env_file=None, openai_api_key="sk-x", retrieval_mode="fuzzy")


def test_hybrid_mode_works_through_the_chat_pipeline(settings, embeddings, chat_model, web):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(settings.model_copy(update={"retrieval_mode": "hybrid"}), embeddings=embeddings, chat_model=chat_model, web_search=web)
    with TestClient(app) as c:
        c.post("/api/documents/upload", files={"file": ("a.pdf", make_pdf(["Error code XJ4471 means overheating."]), "application/pdf")})
        body = c.post("/api/chat", json={"question": "what does XJ4471 mean"}).json()
    assert body["citations"] and body["retrieval_path"][1] == "retrieve_documents"


def test_stored_messages_keep_retrieval_path_and_artifact(client, chat_model):
    from app.agent.schemas import IntentResult
    client.post("/api/documents/upload", files={"file": ("a.pdf", make_pdf(["Mitochondria produce ATP."]), "application/pdf")})
    first = client.post("/api/chat", json={"question": "What do mitochondria produce?"}).json()
    msgs = client.get(f"/api/conversations/{first['conversation_id']}").json()["messages"]
    assert msgs[1]["retrieval_path"] == first["retrieval_path"]

    chat_model.responders["IntentResult"] = lambda m: IntentResult(
        topic=None, intent="quiz", wants_web=False, standalone_question="quiz me")
    quiz = client.post("/api/chat", json={"question": "Quiz me", "conversation_id": first["conversation_id"]}).json()
    last = client.get(f"/api/conversations/{first['conversation_id']}").json()["messages"][-1]
    assert last["artifact"] == quiz["artifact"] and last["retrieval_path"] == ["classify_intent", "generate_quiz"]
