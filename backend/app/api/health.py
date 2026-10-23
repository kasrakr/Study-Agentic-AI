from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app import __version__
from app.config import Settings
from app.dependencies import get_app_settings, get_document_service
from app.services.document_service import DocumentService
from app.services.openai_check import verify_openai

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health(
    settings: Settings = Depends(get_app_settings),
    documents: DocumentService = Depends(get_document_service),
) -> dict:
    """Cheap liveness check; makes no OpenAI calls. Never returns key values."""
    return {
        "status": "ok",
        "version": __version__,
        "openai_configured": settings.openai_configured,
        "tavily_configured": settings.tavily_configured,
        "openai_base_url": settings.openai_base_url,
        "chat_model": settings.openai_chat_model,
        "embedding_model": settings.openai_embedding_model,
        "indexed_documents": documents.count_indexed(),
    }


@router.get("/openai")
def health_openai(request: Request, settings: Settings = Depends(get_app_settings)) -> dict:
    """Makes two tiny real API calls to verify the key, models and billing."""
    result = verify_openai(settings, request.app.state.embeddings, request.app.state.chat_model)
    result["ok"] = result["embedding"]["ok"] and result["chat"]["ok"]
    return result
