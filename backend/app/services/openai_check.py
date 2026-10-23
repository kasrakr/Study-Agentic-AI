"""Verify the OpenAI connection (used by GET /api/health/openai and the CLI)."""

from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from app.config import Settings
from app.errors import AppError
from app.resilience import call_openai


def _probe(fn, retries: int) -> dict:  # noqa: ANN001
    try:
        call_openai(fn, max_retries=retries)
        return {"ok": True, "error": None}
    except AppError as err:
        return {"ok": False, "error": {"code": err.code, "message": err.message}}


def verify_openai(settings: Settings, embeddings: Embeddings, chat_model: BaseChatModel) -> dict:
    """Make one tiny embedding call and one tiny chat call (a few tokens each)."""
    return {
        "embedding": {"model": settings.openai_embedding_model,
                      **_probe(lambda: embeddings.embed_query("ping"), settings.openai_max_retries)},
        "chat": {"model": settings.openai_chat_model,
                 **_probe(lambda: chat_model.invoke("Reply with the single word: ok"), settings.openai_max_retries)},
    }
