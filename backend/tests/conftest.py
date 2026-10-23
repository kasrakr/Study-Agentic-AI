from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings

from app.config import Settings
from app.main import create_app
from app.services.qa_service import GroundedAnswer

DIM = 256
TEST_KEY = "sk-test-0123456789abcdef"


class FakeEmbeddings(Embeddings):
    """Deterministic bag-of-words embeddings so retrieval is testable offline."""

    def __init__(self) -> None:
        self.calls = 0
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
        if self.fail_with:
            raise self.fail_with
        return self._vec(text)


class _Structured:
    def __init__(self, parent: FakeChatModel) -> None:
        self.parent = parent

    def invoke(self, messages):  # noqa: ANN001
        self.parent.calls += 1
        self.parent.last_messages = messages
        if self.parent.fail_with:
            raise self.parent.fail_with
        return self.parent.responder(messages)


class FakeChatModel:
    """Stands in for ChatOpenAI; only the surface the app uses."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_messages = None
        self.fail_with: Exception | None = None
        self.responder: Callable = lambda messages: GroundedAnswer(
            answer_found=True, answer="Answer [1]", cited_sources=[1], limitations=None
        )

    def with_structured_output(self, schema):  # noqa: ANN001
        return _Structured(self)

    def invoke(self, prompt):  # noqa: ANN001
        self.calls += 1
        return "ok"


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
def client(settings: Settings, embeddings: FakeEmbeddings, chat_model: FakeChatModel) -> Iterator[TestClient]:
    app = create_app(settings, embeddings=embeddings, chat_model=chat_model)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    # Retry backoff must never slow the suite down.
    monkeypatch.setattr("app.resilience.time.sleep", lambda _s: None)
