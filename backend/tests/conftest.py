from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings

from app.config import Settings
from app.main import create_app
from app.agent.schemas import (
    DocumentGrade,
    IntentResult,
    MissingInfoPlan,
    RewrittenQuery,
    WebEvidenceGrade,
    WebResultGrade,
)
from app.schemas.flashcards import FlashcardDraft, FlashcardSet
from app.schemas.quizzes import ItemGrade, QuizDraft, QuizQuestionDraft, ShortAnswerGrades
from app.services.web_search import WebResult
from langchain_core.messages import AIMessageChunk

DIM = 256
TEST_KEY = "sk-test-0123456789abcdef"


class FakeEmbeddings(Embeddings):
    """Deterministic bag-of-words embeddings so retrieval is testable offline."""

    def __init__(self) -> None:
        self.calls = 0
        self.queries: list[str] = []
        self.fail_with: Exception | None = None

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.fail_with:
            raise self.fail_with
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        self.queries.append(text)
        if self.fail_with:
            raise self.fail_with
        return self._vec(text)


def mc(question="Which organelle produces ATP?", correct="Mitochondria", source=1, **kw):
    return QuizQuestionDraft(
        type="multiple_choice", question=question, options=[correct, "Ribosome", "Nucleus", "Golgi"],
        correct_option_index=0, correct_boolean=None, reference_answer=None, key_points=[],
        explanation="Mitochondria make ATP.", source_number=source, topic="Cell energy", **kw)


def tf(question="Mitochondria produce ATP.", value=True, source=1):
    return QuizQuestionDraft(
        type="true_false", question=question, options=[], correct_option_index=None, correct_boolean=value,
        reference_answer=None, key_points=[], explanation="Stated in the notes.", source_number=source, topic="ATP")


def sa(question="Explain what mitochondria do.", points=("makes ATP", "uses respiration"), source=1):
    return QuizQuestionDraft(
        type="short_answer", question=question, options=[], correct_option_index=None, correct_boolean=None,
        reference_answer="They make ATP via respiration.", key_points=list(points),
        explanation="Respiration produces ATP.", source_number=source, topic="Respiration")


class _Structured:
    def __init__(self, parent: "FakeChatModel", name: str) -> None:
        self.parent, self.name = parent, name

    def invoke(self, messages):  # noqa: ANN001
        self.parent.calls[self.name] += 1
        self.parent.prompts[self.name] = messages
        if self.parent.fail_with:
            raise self.parent.fail_with
        return self.parent.responders[self.name](messages)


class FakeChatModel:
    """Stands in for ChatOpenAI. Structured calls are answered per schema name by
    `responders` (tests override entries); `stream` yields `stream_text`."""

    def __init__(self) -> None:
        self.calls: Counter = Counter()
        self.prompts: dict[str, list] = {}
        self.fail_with: Exception | None = None
        self.stream_text: str | Callable = "Answer based on the sources [D1]."
        self.responders: dict[str, Callable] = {
            "IntentResult": lambda m: IntentResult(topic=None, intent="study_question", wants_web=False, standalone_question=""),
            "DocumentGrade": lambda m: DocumentGrade(
                verdict="sufficient", reason="The passages answer it.", relevant_passages=[1],
                missing_information=[], retrieval_may_have_missed=False),
            "MissingInfoPlan": lambda m: MissingInfoPlan(
                missing_information=["the missing part"], web_search_query="generic web query"),
            "RewrittenQuery": lambda m: RewrittenQuery(query="rewritten alternative wording"),
            "QuizDraft": lambda m: QuizDraft(questions=[mc("Q one?"), tf("Statement two."), mc("Q three?")]),
            "FlashcardSet": lambda m: FlashcardSet(cards=[
                FlashcardDraft(front="ATP", back="Energy currency.", source_number=1, topic="Energy"),
                FlashcardDraft(front="Mitochondria", back="Make ATP.", source_number=1, topic="Cells")]),
            "ShortAnswerGrades": lambda m: ShortAnswerGrades(
                grades=[ItemGrade(item=1, key_point_results=[True, True], feedback="Good.")]),
            "WebEvidenceGrade": lambda m: WebEvidenceGrade(
                results=[WebResultGrade(index=1, relevant=True, reliability="high"),
                         WebResultGrade(index=2, relevant=True, reliability="medium")],
                coverage="full", reason="Covers it."),
        }

    def with_structured_output(self, schema):  # noqa: ANN001
        return _Structured(self, schema.__name__)

    def stream(self, messages):  # noqa: ANN001
        self.calls["stream"] += 1
        self.prompts["stream"] = messages
        if self.fail_with:
            raise self.fail_with
        text = self.stream_text(messages) if callable(self.stream_text) else self.stream_text
        for piece in re.findall(r"\S+\s*", text):
            yield AIMessageChunk(content=piece)

    def invoke(self, prompt):  # noqa: ANN001
        self.calls["invoke"] += 1
        return "ok"


class FakeWebSearch:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.fail_with: Exception | None = None
        self.results: list[WebResult] = [
            WebResult(title="Osmosis - Encyclopedia", url="https://example.edu/osmosis",
                      content="Osmosis is the movement of water across a membrane.", score=0.9),
            WebResult(title="Biology Notes", url="https://example.org/bio",
                      content="Water moves from low to high solute concentration.", score=0.7),
        ]

    def search(self, query: str, *, max_results: int) -> list[WebResult]:
        self.calls.append((query, max_results))
        if self.fail_with:
            raise self.fail_with
        return self.results[:max_results]


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in lines:
            events.append((lines["event"], json.loads(lines["data"])))
    return events


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(40, 40, 555, 800), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key=TEST_KEY,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        chroma_persist_directory=str(tmp_path / "vectors"),
        upload_directory=str(tmp_path / "uploads"),
        checkpoint_database=str(tmp_path / "checkpoints.sqlite"),
        max_upload_size_mb=1,
        chunk_size=300,
        chunk_overlap=50,
        retrieval_top_k=4,
        openai_max_retries=2,
    )


@pytest.fixture
def embeddings() -> FakeEmbeddings:
    return FakeEmbeddings()


@pytest.fixture
def chat_model() -> FakeChatModel:
    return FakeChatModel()


@pytest.fixture
def web() -> FakeWebSearch:
    return FakeWebSearch()


@pytest.fixture
def client(settings: Settings, embeddings: FakeEmbeddings, chat_model: FakeChatModel, web: FakeWebSearch) -> Iterator[TestClient]:
    app = create_app(settings, embeddings=embeddings, chat_model=chat_model, web_search=web)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    # Retry backoff must never slow the suite down.
    monkeypatch.setattr("app.resilience.time.sleep", lambda _s: None)
