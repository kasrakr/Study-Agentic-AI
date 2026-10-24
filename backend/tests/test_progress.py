from app.schemas.quizzes import QuizDraft
from tests.conftest import make_pdf, mc, tf


def upload(client, name="bio.pdf", pages=None):
    pages = pages or ["Mitochondria produce ATP.", "Ribosomes build proteins."]
    res = client.post("/api/documents/upload", files={"file": (name, make_pdf(pages), "application/pdf")})
    assert res.status_code == 201
    return res.json()["document"]


def topic(q, label):
    return q.model_copy(update={"topic": label})


def take(client, chat_model, doc, questions, wrong: set[int]):
    """Generate a quiz of the given drafts and answer; indexes in `wrong` are answered incorrectly."""
    chat_model.responders["QuizDraft"] = lambda m: QuizDraft(questions=list(questions))
    quiz = client.post("/api/quizzes/generate", json={"document_ids": [doc["id"]], "question_count": len(questions),
                                                       "question_types": ["multiple_choice", "true_false"]}).json()
    answers = []
    for i, q in enumerate(quiz["questions"]):
        if q["type"] == "true_false":
            answers.append({"question_id": q["id"], "boolean_answer": (i not in wrong)})  # draft says True
        else:
            right = q["options"].index("Mitochondria")
            answers.append({"question_id": q["id"], "selected_option": (right + 1) % 4 if i in wrong else right})
    return client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": answers}).json()


def progress(client):
    return client.get("/api/progress").json()


def test_empty_state_makes_no_claims(client):
    p = progress(client)
    assert p["indexed_documents"] == 0 and p["quiz"] == {"attempts": 0, "average_score_percent": None, "best_score_percent": None, "recent": []}
    assert p["weak_topics"] == [] and "nothing to base" in p["weak_topics_note"] and p["suggestions"] == []
    assert "at least 2 results" in p["weak_topics_method"]  # the rule is shown to the student


def test_quiz_stats_and_recent_attempts(client, chat_model):
    doc = upload(client)
    take(client, chat_model, doc, [mc("A?"), mc("B?")], wrong=set())       # 100%
    take(client, chat_model, doc, [mc("C?"), mc("D?")], wrong={0, 1})      # 0%
    p = progress(client)
    assert p["indexed_documents"] == 1
    assert (p["quiz"]["attempts"], p["quiz"]["average_score_percent"], p["quiz"]["best_score_percent"]) == (2, 50.0, 100.0)
    assert [r["score_percent"] for r in p["quiz"]["recent"]] == [0.0, 100.0]  # newest first
    kinds = {a["type"] for a in p["recent_activity"]}
    assert {"upload", "quiz"} <= kinds


def test_weak_topic_is_flagged_only_with_enough_evidence_and_links_documents(client, chat_model):
    doc = upload(client)
    # One wrong answer on "Respiration" is a single data point: not enough to flag.
    take(client, chat_model, doc, [topic(mc("A?"), "Respiration"), topic(mc("B?"), "Genetics")], wrong={0})
    assert progress(client)["weak_topics"] == []
    # A second wrong answer on the same topic crosses the threshold (2 of 2 wrong).
    take(client, chat_model, doc, [topic(mc("C?"), "respiration"), topic(mc("D?"), "Genetics")], wrong={0})
    p = progress(client)
    assert [w["topic"] for w in p["weak_topics"]] == ["Respiration"]  # labels merged case-insensitively
    w = p["weak_topics"][0]
    assert (w["data_points"], w["incorrect_answers"], w["weak_share"]) == (2, 2, 1.0)
    assert w["documents"] == [{"document_id": doc["id"], "filename": "bio.pdf"}]
    assert p["suggestions"][0]["topic"] == "Respiration" and p["suggestions"][0]["document_ids"] == [doc["id"]]
    assert "2 incorrect" in p["suggestions"][0]["reason"]


def test_mostly_correct_topics_are_not_flagged(client, chat_model):
    doc = upload(client)
    take(client, chat_model, doc, [topic(mc(f"Q{i}?"), "Cells") for i in range(4)], wrong={0})  # 1 of 4 wrong
    assert progress(client)["weak_topics"] == []


def test_difficult_flashcards_count_toward_weak_topics(client, chat_model):
    from app.schemas.flashcards import FlashcardDraft, FlashcardSet
    doc = upload(client)
    chat_model.responders["FlashcardSet"] = lambda m: FlashcardSet(cards=[
        FlashcardDraft(front="F1", back="B1", source_number=1, topic="Enzymes"),
        FlashcardDraft(front="F2", back="B2", source_number=1, topic="Enzymes"),
        FlashcardDraft(front="F3", back="B3", source_number=1, topic="Cells")])
    deck = client.post("/api/flashcards/generate", json={"document_ids": [doc["id"]], "card_count": 3}).json()
    for card, rating in zip(deck["cards"], ["difficult", "difficult", "easy"]):
        client.put(f"/api/flashcards/cards/{card['id']}/difficulty", json={"difficulty": rating})
    p = progress(client)
    assert p["flashcards"] == {"decks": 1, "rated": 3, "easy": 1, "medium": 0, "difficult": 2}
    assert [(w["topic"], w["difficult_cards"]) for w in p["weak_topics"]] == [("Enzymes", 2)]
    assert "flashcards" in {a["type"] for a in p["recent_activity"]}


def test_unanswered_questions_are_not_counted_as_wrong(client, chat_model):
    doc = upload(client)
    chat_model.responders["QuizDraft"] = lambda m: QuizDraft(questions=[topic(mc("A?"), "Cells"), topic(tf("B."), "Cells")])
    quiz = client.post("/api/quizzes/generate", json={"document_ids": [doc["id"]], "question_count": 2,
                                                       "question_types": ["multiple_choice", "true_false"]}).json()
    client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": []})
    assert progress(client)["weak_topics"] == []


def test_deleted_documents_disappear_from_weak_topic_links(client, chat_model):
    doc = upload(client)
    take(client, chat_model, doc, [topic(mc("A?"), "Cells"), topic(mc("B?"), "Cells")], wrong={0, 1})
    client.delete(f"/api/documents/{doc['id']}")
    p = progress(client)
    assert p["weak_topics"][0]["documents"] == [] and p["suggestions"] == []  # no suggestion without a document to practise on


def test_chat_activity_is_listed(client):
    upload(client)
    client.post("/api/chat", json={"question": "What do mitochondria produce?"})
    assert any(a["type"] == "chat" for a in progress(client)["recent_activity"])
