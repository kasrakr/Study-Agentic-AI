from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_chat_service, get_document_service
from app.schemas.chat import ChatRequest, ChatResponse, ConversationDetail, ConversationList
from app.schemas.common import ErrorResponse
from app.schemas.documents import DeleteResponse
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/chat", tags=["chat"])
conversations = APIRouter(prefix="/api/conversations", tags=["conversations"])

_ERRORS = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}}


@router.post("", response_model=ChatResponse, responses=_ERRORS)
def chat(
    body: ChatRequest,
    documents: DocumentService = Depends(get_document_service),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """Ask a question. Uploaded documents are searched first; the web is used only if
    they don't contain enough evidence (or the student explicitly asks for it)."""
    if body.document_ids:
        documents.require_indexed(body.document_ids)
    return service.answer(body.question, body.conversation_id, body.document_ids)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream", responses={200: {"content": {"text/event-stream": {}}}, **_ERRORS})
def chat_stream(
    body: ChatRequest,
    documents: DocumentService = Depends(get_document_service),
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """Server-Sent Events: `status`, `token`, `sources`, `done`, or `error`.

    Status events report steps the backend actually ran; they contain no model reasoning.
    Request validation errors are returned as normal HTTP errors before the stream starts.
    """
    if body.document_ids:
        documents.require_indexed(body.document_ids)

    def events() -> Iterator[str]:
        for event, data in service.stream(body.question, body.conversation_id, body.document_ids):
            yield _sse(event, data)

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@conversations.get("", response_model=ConversationList)
def list_conversations(service: ChatService = Depends(get_chat_service)) -> ConversationList:
    return ConversationList(conversations=service.list_conversations())


@conversations.get("/{conversation_id}", response_model=ConversationDetail, responses=_ERRORS)
def get_conversation(conversation_id: str, service: ChatService = Depends(get_chat_service)) -> ConversationDetail:
    return service.get_conversation(conversation_id)


@conversations.delete("/{conversation_id}", response_model=DeleteResponse, responses=_ERRORS)
def delete_conversation(conversation_id: str, service: ChatService = Depends(get_chat_service)) -> DeleteResponse:
    service.delete_conversation(conversation_id)
    return DeleteResponse(id=conversation_id, deleted=True)
