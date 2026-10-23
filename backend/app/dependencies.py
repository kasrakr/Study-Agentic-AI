"""FastAPI dependencies. Shared objects are created once in the app lifespan
and read from `app.state`, which also makes them easy to substitute in tests."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.config import Settings
from app.rag.indexer import VectorIndex
from app.services.document_service import DocumentService


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
