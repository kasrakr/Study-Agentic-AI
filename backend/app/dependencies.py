"""FastAPI dependencies. Shared objects are created once in the app lifespan
and read from `app.state`, which also makes them easy to substitute in tests."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.config import Settings
from app.rag.indexer import VectorIndex
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.flashcard_service import FlashcardService
from app.services.quiz_service import QuizService


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_vector_index(request: Request) -> VectorIndex:
    return request.app.state.vector_index


def get_chat_model(request: Request) -> BaseChatModel:
    return request.app.state.chat_model


def get_document_service(
    db: Session = Depends(get_db),
    index: VectorIndex = Depends(get_vector_index),
    settings: Settings = Depends(get_app_settings),
) -> DocumentService:
    return DocumentService(db, index, settings)


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_quiz_service(
    db: Session = Depends(get_db),
    index: VectorIndex = Depends(get_vector_index),
    chat_model: BaseChatModel = Depends(get_chat_model),
    settings: Settings = Depends(get_app_settings),
) -> QuizService:
    return QuizService(db, index, chat_model, settings)


def get_flashcard_service(
    db: Session = Depends(get_db),
    index: VectorIndex = Depends(get_vector_index),
    chat_model: BaseChatModel = Depends(get_chat_model),
    settings: Settings = Depends(get_app_settings),
) -> FlashcardService:
    return FlashcardService(db, index, chat_model, settings)
