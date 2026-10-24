"""One continuous student journey through the real application stack (fake model, embeddings and web search).

Each step corresponds to an item in the project's Definition of Done.
"""

from app.agent.schemas import DocumentGrade
from app.schemas.quizzes import QuizDraft
from tests.conftest import make_pdf, mc, parse_sse, tf


def grade(verdict, missing=()):
    return lambda m: DocumentGrade(verdict=verdict, reason=f"{verdict}.", relevant_passages=[1] if verdict != "insufficient" else [],
                                   missing_information=list(missing), retrieval_may_have_missed=False)


def test_full_student_journey(client, chat_model, web, settings):
    # The student can upload a PDF, and it is indexed persistently.
    pdf = make_pdf(["Mitochondria produce ATP through cellular respiration.", "Ribosomes build proteins from messenger RNA."])
    up = client.post("/api/documents/upload", files={"file": ("Biology.pdf", pdf, "application/pdf")})
    assert up.status_code == 201
    doc = up.json()["document"]
    assert doc["status"] == "indexed" and doc["page_count"] == 2 and doc["chunk_count"] >= 2
    assert client.app.state.vector_index.count_for_document(doc["id"]) == doc["chunk_count"]
    assert (settings.upload_path / f"{doc['id']}.pdf").exists()

    # The student asks about the PDF: documents are searched first, Tavily is not used, the citation is traceable.
    chat_model.stream_text = "Mitochondria produce ATP [D1]."
    first = client.post("/api/chat", json={"question": "What do mitochondria produce?"}).json()
    assert first["retrieval_path"][1] == "retrieve_documents" and first["web_search_used"] is False and web.calls == []
    cite = first["citations"][0]
    assert (cite["source_type"], cite["filename"], cite["page_number"]) == ("document", "Biology.pdf", 1)
    page_link = client.get(f"/api/documents/{cite['document_id']}/file")  # the citation's target is a real file
    assert page_link.status_code == 200 and page_link.content.startswith(b"%PDF")
    assert first["answer_origin"] == "documents"

    # Evidence is insufficient: web search runs for the missing part only, and origins stay distinguishable.
    chat_model.responders["DocumentGrade"] = grade("partial", missing=["osmosis"])
    chat_model.stream_text = "Your notes cover ATP [D1]. A web source explains osmosis [W1]."
    mixed = client.post("/api/chat", json={"question": "Explain ATP and osmosis", "conversation_id": first["conversation_id"]}).json()
    assert mixed["web_search_used"] is True and len(web.calls) == 1 and mixed["answer_origin"] == "documents_and_web"
    kinds = {c["marker"]: c["source_type"] for c in mixed["citations"]}
    assert kinds == {"D1": "document", "W1": "web"}
    assert next(c for c in mixed["citations"] if c["marker"] == "W1")["url"].startswith("https://")

    # Streaming reports the same path through real statuses.
    chat_model.responders["DocumentGrade"] = grade("sufficient")
    chat_model.stream_text = "ATP [D1]."
    events = parse_sse(client.post("/api/chat/stream", json={"question": "What do mitochondria produce?"}).text)
    assert [e for e, _ in events][-2:] == ["sources", "done"] and len(web.calls) == 1  # no extra web call

    # Conversation history persisted and isolated.
    history = client.get(f"/api/conversations/{first['conversation_id']}").json()["messages"]
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert len(client.get("/api/conversations").json()["conversations"]) == 2

    # Quiz from uploaded material; submission produces stored results.
    chat_model.responders["QuizDraft"] = lambda m: QuizDraft(questions=[mc("Which organelle makes ATP?"), tf("Ribosomes make ATP.", value=False)])
    quiz = client.post("/api/quizzes/generate", json={"document_ids": [doc["id"]], "question_count": 2,
                                                       "question_types": ["multiple_choice", "true_false"]}).json()
    assert "explanation" not in quiz["questions"][0] and len(quiz["questions"]) == 2
    answers = [{"question_id": quiz["questions"][0]["id"], "selected_option": quiz["questions"][0]["options"].index("Mitochondria")},
               {"question_id": quiz["questions"][1]["id"], "boolean_answer": True}]  # one right, one wrong
    result = client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": answers}).json()
    assert result["score_percent"] == 50.0 and result["results"][0]["source"]["filename"] == "Biology.pdf"

    # Flashcards can be generated and reviewed.
    deck = client.post("/api/flashcards/generate", json={"document_ids": [doc["id"]], "card_count": 2}).json()
    assert client.put(f"/api/flashcards/cards/{deck['cards'][0]['id']}/difficulty", json={"difficulty": "difficult"}).status_code == 200

    # Progress reflects everything that happened.
    progress = client.get("/api/progress").json()
    assert progress["indexed_documents"] == 1 and progress["quiz"]["attempts"] == 1 and progress["flashcards"]["difficult"] == 1
    assert {a["type"] for a in progress["recent_activity"]} >= {"upload", "chat", "quiz", "flashcards"}

    # Deleting the document removes its vectors, file and metadata; later questions can't cite it.
    assert client.delete(f"/api/documents/{doc['id']}").status_code == 200
    assert client.app.state.vector_index.count_for_document(doc["id"]) == 0
    assert not (settings.upload_path / f"{doc['id']}.pdf").exists()
    chat_model.responders["DocumentGrade"] = grade("sufficient")
    after = client.post("/api/chat", json={"question": "What do mitochondria produce?"}).json()
    assert not [c for c in after["citations"] if c["source_type"] == "document"]  # the deleted document can't be cited
    assert "[D1]" not in after["answer"]  # and the model's stale marker was stripped
    assert after["answer_origin"] in ("web", "none")

    # No secret ever appeared in any response body we saw.
    assert settings.openai_api_key.get_secret_value() not in str([first, mixed, result, progress, events])
