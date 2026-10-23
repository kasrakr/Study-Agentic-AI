import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app.agent.schemas import DocumentGrade, IntentResult
from app.errors import AppError
from app.main import create_app
from app.resilience import stream_text
from tests.conftest import FakeChatModel, FakeEmbeddings, FakeWebSearch, make_pdf, parse_sse


def upload(client, name="bio.pdf", pages=None):
    pages = pages or ["Cells are small.", "Mitochondria produce ATP through cellular respiration."]
    res = client.post("/api/documents/upload", files={"file": (name, make_pdf(pages), "application/pdf")})
    assert res.status_code == 201
    return res.json()["document"]


def stream(client, question="What do mitochondria produce?", **extra):
    res = client.post("/api/chat/stream", json={"question": question, **extra})
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/event-stream")
    return parse_sse(res.text)


def statuses(events, phase="started"):
    return [d["status"] for e, d in events if e == "status" and d["phase"] == phase]


# ---------------------------------------------------------------- SSE

def test_stream_emits_real_statuses_tokens_sources_done_in_order(client, chat_model, web):
    upload(client)
    chat_model.stream_text = "Mitochondria make ATP [D1]."
    events = stream(client)
    kinds = [e for e, _ in events]
    assert kinds[-2:] == ["sources", "done"] and kinds.count("sources") == kinds.count("done") == 1
    assert statuses(events) == ["classifying_question", "retrieving_documents", "evaluating_evidence", "generating_answer"]
    assert "searching_web" not in statuses(events) and web.calls == []  # statuses mirror what actually ran
    assert statuses(events, "completed") == statuses(events)
    tokens = "".join(d["text"] for e, d in events if e == "token")
    assert tokens == "Mitochondria make ATP [D1]."
    # all status events precede the first token for the answer step
    assert kinds.index("token") > max(i for i, k in enumerate(kinds) if k == "status" and events[i][1]["status"] == "evaluating_evidence")
    sources = dict(events)["sources"]
    assert sources["answer_origin"] == "documents" and sources["citations"][0]["filename"] == "bio.pdf"
    done = dict(events)["done"]
    assert done["retrieval_path"] == ["classify_intent", "retrieve_documents", "grade_document_evidence", "generate_answer"]
    assert done["conversation_id"]


def test_stream_reports_web_search_when_it_really_happens(client, chat_model, web):
    upload(client)
    chat_model.responders["DocumentGrade"] = lambda m: DocumentGrade(
        verdict="partial", reason="r", relevant_passages=[1], missing_information=["x"], retrieval_may_have_missed=False)
    chat_model.stream_text = "Notes [D1]. Web [W1]."
    events = stream(client)
    assert "searching_web" in statuses(events) and len(web.calls) == 1
    detail = [d["detail"] for e, d in events if e == "status" and d["status"] == "searching_web" and d["phase"] == "completed"]
    assert detail == ["2 results"]
    assert dict(events)["sources"]["web_search_used"] is True


def test_sources_event_carries_the_cleaned_final_text(client, chat_model):
    upload(client)
    chat_model.stream_text = "Real [D1] and fake [D9]."
    events = stream(client)
    assert "".join(d["text"] for e, d in events if e == "token") == "Real [D1] and fake [D9]."
    assert dict(events)["sources"]["answer"] == "Real [D1] and fake."


def test_provider_error_mid_run_becomes_a_sanitized_error_event(client, chat_model):
    upload(client)
    chat_model.fail_with = openai.AuthenticationError(
        "bad key sk-leaked-123456", body=None, response=httpx.Response(401, request=httpx.Request("POST", "https://x")))
    events = stream(client)
    kinds = [e for e, _ in events]
    assert kinds[-1] == "error" and "sources" not in kinds and "done" not in kinds
    assert events[-1][1]["code"] == "openai_auth_failed" and "sk-leaked" not in str(events)


def test_unexpected_exception_in_stream_does_not_leak_internals(client, chat_model):
    chat_model.responders["IntentResult"] = lambda m: (_ for _ in ()).throw(RuntimeError("secret internals"))
    events = stream(client)
    assert events[-1][0] == "error" and "secret internals" not in str(events)


def test_validation_errors_are_normal_http_errors_before_streaming(client):
    assert client.post("/api/chat/stream", json={"question": ""}).status_code == 422
    assert client.post("/api/chat/stream", json={"question": "q", "document_ids": ["doc_nope"]}).status_code == 404


def test_smalltalk_streams_without_retrieval(client, chat_model):
    chat_model.responders["IntentResult"] = lambda m: IntentResult(topic=None, intent="smalltalk", wants_web=False, standalone_question="hi")
    events = stream(client, "hello")
    assert statuses(events) == ["classifying_question", "responding"]
    assert dict(events)["done"]["evidence_found"] is False


# ---------------------------------------------------------------- stream_text retry rules

class _Flaky:
    def __init__(self, fail_after_tokens: int, errors: int):
        self.fail_after, self.errors, self.attempts = fail_after_tokens, errors, 0

    def stream(self, messages):
        from langchain_core.messages import AIMessageChunk
        self.attempts += 1
        for i in range(3):
            if i == self.fail_after and self.attempts <= self.errors:
                raise openai.APIConnectionError(request=httpx.Request("POST", "https://x"))
            yield AIMessageChunk(content=f"t{i} ")


def test_stream_retries_only_before_any_token_is_emitted(monkeypatch):
    monkeypatch.setattr("app.resilience.time.sleep", lambda _s: None)
    seen: list[str] = []
    model = _Flaky(fail_after_tokens=0, errors=1)
    assert stream_text(model, [], on_token=seen.append, max_retries=2) == "t0 t1 t2 "
    assert model.attempts == 2 and seen == ["t0 ", "t1 ", "t2 "]  # no duplicated tokens

    seen2: list[str] = []
    model2 = _Flaky(fail_after_tokens=1, errors=1)  # fails after "t0" was already shown
    with pytest.raises(AppError) as info:
        stream_text(model2, [], on_token=seen2.append, max_retries=2)
    assert info.value.code == "openai_connection_error" and model2.attempts == 1 and seen2 == ["t0 "]


# ---------------------------------------------------------------- conversations

def chat(client, question, conversation_id=None):
    body = {"question": question, **({"conversation_id": conversation_id} if conversation_id else {})}
    res = client.post("/api/chat", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def test_conversation_history_is_stored_with_citations_and_listed(client, chat_model):
    upload(client)
    chat_model.stream_text = "ATP [D1]."
    first = chat(client, "What do mitochondria produce?")
    cid = first["conversation_id"]
    chat(client, "And where?", cid)

    detail = client.get(f"/api/conversations/{cid}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    assert detail["messages"][0]["content"] == "What do mitochondria produce?"
    assistant = detail["messages"][1]
    assert assistant["citations"][0]["filename"] == "bio.pdf" and assistant["answer_origin"] == "documents"
    assert detail["conversation"]["title"] == "What do mitochondria produce?"
    listing = client.get("/api/conversations").json()["conversations"]
    assert [c["id"] for c in listing] == [cid]


def test_follow_up_receives_earlier_turns_as_history(client, chat_model):
    upload(client)
    cid = chat(client, "What do mitochondria produce?")["conversation_id"]
    chat(client, "and where?", cid)
    history_prompt = chat_model.prompts["IntentResult"][1].content
    assert "What do mitochondria produce?" in history_prompt and "Student:" in history_prompt


def test_conversations_never_share_messages_or_history(client, chat_model):
    upload(client)
    a = chat(client, "Question in conversation A about mitochondria")["conversation_id"]
    b = chat(client, "Question in conversation B", None)["conversation_id"]
    assert a != b
    assert "conversation A" not in chat_model.prompts["IntentResult"][1].content  # B's classifier saw no A history
    msgs_b = client.get(f"/api/conversations/{b}").json()["messages"]
    assert [m["content"] for m in msgs_b if m["role"] == "user"] == ["Question in conversation B"]


def test_each_turn_reports_only_its_own_execution_events(client):
    upload(client)
    first = chat(client, "What do mitochondria produce?")
    second = chat(client, "And more?", first["conversation_id"])
    assert second["retrieval_path"] == first["retrieval_path"]  # not accumulated across turns


def test_conversations_survive_an_app_restart(settings, embeddings, chat_model, web):
    def new_app():
        return TestClient(create_app(settings, embeddings=embeddings, chat_model=chat_model, web_search=web))

    with new_app() as c1:
        upload(c1)
        cid = chat(c1, "What do mitochondria produce?")["conversation_id"]
    with new_app() as c2:
        detail = c2.get(f"/api/conversations/{cid}").json()
        assert len(detail["messages"]) == 2 and detail["messages"][1]["citations"]
        chat(c2, "Follow-up after restart", cid)
        assert len(c2.get(f"/api/conversations/{cid}").json()["messages"]) == 4


def test_delete_conversation_removes_row_and_checkpoint(client):
    upload(client)
    cid = chat(client, "What do mitochondria produce?", "keepme")["conversation_id"]
    assert client.delete(f"/api/conversations/{cid}").json() == {"id": cid, "deleted": True}
    assert client.get(f"/api/conversations/{cid}").status_code == 404
    assert client.delete(f"/api/conversations/{cid}").status_code == 404
    chat(client, "Fresh start", cid)  # same id is reusable and starts empty
    assert len(client.get(f"/api/conversations/{cid}").json()["messages"]) == 2


def test_unknown_conversation_is_404(client):
    res = client.get("/api/conversations/nope")
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"


def test_streaming_turns_are_persisted_too(client):
    upload(client)
    events = stream(client, "What do mitochondria produce?", conversation_id="streamed-1")
    assert dict(events)["done"]["conversation_id"] == "streamed-1"
    assert len(client.get("/api/conversations/streamed-1").json()["messages"]) == 2


# ---------------------------------------------------------------- document file links

def test_original_file_is_served_inline_for_citation_links(client):
    doc = upload(client)
    res = client.get(f"/api/documents/{doc['id']}/file")
    assert res.status_code == 200 and res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"].startswith("inline") and res.content.startswith(b"%PDF")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/documents/doc_nope/file").status_code == 404
