from app.agent.routing import route_after_classify
from app.agent.schemas import IntentResult
from app.schemas.flashcards import FlashcardDraft, FlashcardSet
from tests.conftest import make_pdf, parse_sse


def upload(client, name="bio.pdf", pages=None):
    pages = pages or ["Mitochondria produce ATP through respiration.", "Ribosomes build proteins from RNA."]
    res = client.post("/api/documents/upload", files={"file": (name, make_pdf(pages), "application/pdf")})
    assert res.status_code == 201
    return res.json()["document"]


def card(front="Front", back="Back", source=1, topic="T"):
    return FlashcardDraft(front=front, back=back, source_number=source, topic=topic)


def gen(client, ids, **kw):
    return client.post("/api/flashcards/generate", json={"document_ids": ids, **kw})


# ---------------------------------------------------------------- flashcards

def test_generate_get_and_rate_flashcards(client, chat_model):
    doc = upload(client)
    chat_model.responders["FlashcardSet"] = lambda m: FlashcardSet(cards=[card("ATP?", "Energy currency."), card("Ribosome?", "Builds proteins.")])
    res = gen(client, [doc["id"]], card_count=2)
    assert res.status_code == 201
    deck = res.json()
    assert [c["front"] for c in deck["cards"]] == ["ATP?", "Ribosome?"]
    first = deck["cards"][0]
    assert (first["filename"], first["difficulty"], first["rated_at"]) == ("bio.pdf", None, None)
    assert client.get(f"/api/flashcards/{deck['id']}").json() == deck

    rated = client.put(f"/api/flashcards/cards/{first['id']}/difficulty", json={"difficulty": "difficult"})
    assert rated.status_code == 200 and rated.json()["difficulty"] == "difficult" and rated.json()["rated_at"]
    again = client.get(f"/api/flashcards/{deck['id']}").json()["cards"][0]
    assert again["difficulty"] == "difficult"  # persisted


def test_flashcard_validation_dedupes_drops_invalid_and_trims(client, chat_model):
    doc = upload(client)
    chat_model.responders["FlashcardSet"] = lambda m: FlashcardSet(cards=[
        card("Good?", "Yes."), card("good", "dup front"), card("", "no front"), card("No back", "  "),
        card("Bad source", "x", source=42), card("Second?", "Two."), card("Third?", "Three.")])
    deck = gen(client, [doc["id"]], card_count=2).json()
    assert [c["front"] for c in deck["cards"]] == ["Good?", "Second?"]


def test_flashcards_fail_cleanly_when_nothing_valid_and_validate_requests(client, chat_model):
    doc = upload(client)
    chat_model.responders["FlashcardSet"] = lambda m: FlashcardSet(cards=[card("", "")])
    res = gen(client, [doc["id"]])
    assert res.status_code == 502 and res.json()["error"]["code"] == "flashcard_generation_failed"
    assert chat_model.calls["FlashcardSet"] == 2
    assert gen(client, []).status_code == 422
    assert gen(client, ["doc_missing"]).status_code == 404
    assert gen(client, [doc["id"]], card_count=50).json()["error"]["code"] == "too_many_cards"  # limit is 30


def test_rating_validation_and_unknown_ids(client, chat_model):
    doc = upload(client)
    deck = gen(client, [doc["id"]]).json()
    cid = deck["cards"][0]["id"]
    assert client.put(f"/api/flashcards/cards/{cid}/difficulty", json={"difficulty": "hard"}).status_code == 422
    assert client.put("/api/flashcards/cards/nope/difficulty", json={"difficulty": "easy"}).status_code == 404
    assert client.get("/api/flashcards/nope").status_code == 404


# ---------------------------------------------------------------- chat-driven study tools

def test_routing_sends_quiz_and_flashcard_intents_to_their_nodes():
    assert route_after_classify({"intent": "quiz"}) == "generate_quiz"
    assert route_after_classify({"intent": "flashcards"}) == "generate_flashcards"


def test_chat_can_create_a_quiz_from_documents_without_web_or_retrieval_grading(client, chat_model, web):
    upload(client)
    chat_model.responders["IntentResult"] = lambda m: IntentResult(
        intent="quiz", wants_web=False, topic="mitochondria", standalone_question="quiz me on mitochondria")
    body = client.post("/api/chat", json={"question": "Quiz me on mitochondria"}).json()
    assert body["retrieval_path"] == ["classify_intent", "generate_quiz"]
    assert body["artifact"]["type"] == "quiz" and body["evidence_found"] is True
    assert web.calls == [] and chat_model.calls["DocumentGrade"] == 0
    quiz = client.get(f"/api/quizzes/{body['artifact']['id']}").json()
    assert quiz["question_count"] == 3 and "Focus on: mitochondria" in chat_model.prompts["QuizDraft"][1].content


def test_chat_can_create_flashcards_and_respects_document_selection(client, chat_model):
    a = upload(client, "a.pdf", ["Alpha content about enzymes."])
    upload(client, "b.pdf", ["Beta content about tectonics."])
    chat_model.responders["IntentResult"] = lambda m: IntentResult(
        intent="flashcards", wants_web=False, topic=None, standalone_question="make flashcards")
    body = client.post("/api/chat", json={"question": "Make flashcards", "document_ids": [a["id"]]}).json()
    assert body["artifact"]["type"] == "flashcards"
    deck = client.get(f"/api/flashcards/{body['artifact']['id']}").json()
    assert deck["document_ids"] == [a["id"]]
    human = chat_model.prompts["FlashcardSet"][1].content
    assert "Alpha" in human and "Beta" not in human


def test_chat_quiz_without_documents_explains_instead_of_inventing(client, chat_model):
    chat_model.responders["IntentResult"] = lambda m: IntentResult(
        intent="quiz", wants_web=False, topic=None, standalone_question="quiz me")
    body = client.post("/api/chat", json={"question": "Quiz me"}).json()
    assert body["artifact"] is None and "Upload" in body["answer"] and chat_model.calls["QuizDraft"] == 0


def test_streaming_reports_quiz_generation_status(client, chat_model):
    upload(client)
    chat_model.responders["IntentResult"] = lambda m: IntentResult(
        intent="quiz", wants_web=False, topic=None, standalone_question="quiz me")
    res = client.post("/api/chat/stream", json={"question": "Quiz me"})
    events = parse_sse(res.text)
    assert [d["status"] for e, d in events if e == "status" and d["phase"] == "started"] == ["classifying_question", "generating_quiz"]
    assert dict(events)["done"]["artifact"]["type"] == "quiz"
