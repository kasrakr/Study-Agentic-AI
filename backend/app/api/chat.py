from __future__ import annotations

from fastapi import APIRouter, Depends
from langchain_core.language_models import BaseChatModel

from app.config import Settings
from app.dependencies import (
    get_app_settings,
    get_chat_model,
    get_document_service,
    get_vector_index,
)
from app.rag.indexer import VectorIndex
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import ErrorResponse
from app.services.document_service import DocumentService
from app.services.qa_service import answer_from_documents

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post(
    "", response_model=ChatResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
               502: {"model": ErrorResponse}},
)
def chat(
    body: ChatRequest,
    documents: DocumentService = Depends(get_document_service),
    index: VectorIndex = Depends(get_vector_index),
    chat_model: BaseChatModel = Depends(get_chat_model),
    settings: Settings = Depends(get_app_settings),
) -> ChatResponse:
    """Answer a question from the uploaded documents only (Phase 3).

    Web fallback, conversation memory and streaming arrive in later phases.
    """
    if body.document_ids:
        documents.require_indexed(body.document_ids)
    return answer_from_documents(
        question=body.question, index=index, chat_model=chat_model, settings=settings,
        document_ids=body.document_ids, conversation_id=body.conversation_id,
    )
