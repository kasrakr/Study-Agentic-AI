"""DEVELOPMENT / TEST ONLY: serves the real app with canned fake models and fake web search.

Used to verify scripts/smoke_live.py without API keys. It produces scripted answers, NOT real ones, so never
use it to study.   python scripts/fake_server.py [--port 8766] [--tavily]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import uvicorn  # noqa: E402

from app.agent.schemas import DocumentGrade  # noqa: E402
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.conftest import FakeChatModel, FakeEmbeddings, FakeWebSearch  # noqa: E402


def build(port_cors: str, with_web: bool):
    tmp = Path(tempfile.mkdtemp(prefix="fake-study-"))
    settings = Settings(
        _env_file=None, openai_api_key="sk-fake-not-a-real-key", database_url=f"sqlite:///{tmp / 'app.db'}",
        chroma_persist_directory=str(tmp / "vectors"), upload_directory=str(tmp / "uploads"),
        checkpoint_database=str(tmp / "ckpt.sqlite"), cors_origins=port_cors,
        tavily_api_key="tvly-fake" if with_web else None)

    chat = FakeChatModel()

    def grade(messages) -> DocumentGrade:
        question = messages[1].content.lower()
        covered = "world cup" not in question
        return DocumentGrade(verdict="sufficient" if covered else "insufficient", reason="scripted", relevant_passages=[1] if covered else [],
                             missing_information=[] if covered else ["the answer"], retrieval_may_have_missed=False)

    chat.responders["DocumentGrade"] = grade
    chat.stream_text = lambda m: ("The light reactions occur in the thylakoid membranes [D1]." if "[D1]" in m[1].content or "document_source" in m[1].content
                                  else "A web source says so [W1].")
    return create_app(settings, embeddings=FakeEmbeddings(), chat_model=chat, web_search=FakeWebSearch() if with_web else None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--tavily", action="store_true", help="pretend a Tavily key is configured")
    args = ap.parse_args()
    uvicorn.run(build("http://localhost:5173", args.tavily), port=args.port, log_level="warning")
