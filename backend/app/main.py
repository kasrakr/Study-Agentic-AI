"""FastAPI application factory.

Run with:  uvicorn app.main:create_app --factory --reload
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.sqlite import SqliteSaver
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.agent.graph import build_graph
from app.agent.nodes import AgentDeps
from app.api import chat, documents, flashcards, health, quizzes
from app.config import Settings, get_settings
from app.db.database import create_db_engine, init_db, make_session_factory
from app.errors import AppError
from app.llm import get_chat_model
from app.logging_config import configure_logging
from app.rag.embeddings import get_embeddings
from app.rag.indexer import VectorIndex
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.web_search import TavilySearch, WebSearchProvider

logger = logging.getLogger(__name__)


def _error_response(status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def create_app(
    settings: Settings | None = None,
    *,
    embeddings: Embeddings | None = None,
    chat_model: BaseChatModel | None = None,
    web_search: WebSearchProvider | None | str = "auto",
) -> FastAPI:
    """`embeddings` / `chat_model` / `web_search` let tests inject fakes.

    web_search="auto" builds Tavily from TAVILY_API_KEY (or None if unset);
    passing None explicitly disables the web fallback."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings)
        settings.validate_for_startup()  # fail fast on missing/invalid config
        settings.ensure_directories()

        engine = create_db_engine(settings.sqlalchemy_url)
        init_db(engine)
        session_factory = make_session_factory(engine)

        emb = embeddings or get_embeddings(settings)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.embeddings = emb
        app.state.chat_model = chat_model or get_chat_model(settings, temperature=0.0)
        # Raises EmbeddingModelMismatchError if the persisted index was built
        # with a different embedding model.
        app.state.vector_index = VectorIndex(
            embeddings=emb,
            persist_directory=settings.chroma_path,
            collection_name=settings.chroma_collection_name,
            embedding_model_name=settings.openai_embedding_model,
            max_retries=settings.openai_max_retries,
        )
        if web_search == "auto":
            search: WebSearchProvider | None = (
                TavilySearch(settings.tavily_api_key, timeout_seconds=settings.tavily_timeout_seconds)
                if settings.tavily_api_key is not None else None
            )
        else:
            search = web_search  # type: ignore[assignment]
        app.state.web_search = search

        # Conversation state persists in SQLite so chats survive restarts.
        checkpoint_conn = sqlite3.connect(str(settings.checkpoint_path), check_same_thread=False)
        checkpointer = SqliteSaver(checkpoint_conn)
        graph = build_graph(
            AgentDeps(settings=settings, index=app.state.vector_index, chat_model=app.state.chat_model,
                      web_search=search, session_factory=session_factory),
            checkpointer,
        )
        app.state.chat_service = ChatService(graph, checkpointer, session_factory)

        with session_factory() as session:
            recovered = DocumentService(session, app.state.vector_index, settings).recover_interrupted()
            if recovered:
                logger.warning("Marked %d interrupted document(s) as failed", recovered)
        logger.info(
            "Study AI Agent %s ready (chat=%s, embeddings=%s)",
            __version__, settings.openai_chat_model, settings.openai_embedding_model,
        )
        yield
        checkpoint_conn.close()
        engine.dispose()

    app = FastAPI(
        title="Study AI Agent API", version=__version__, lifespan=lifespan,
        description="Document-first agentic RAG study assistant. Single-user local MVP: "
                    "there is no authentication.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
            for e in exc.errors()
        ]
        return _error_response(422, "validation_error", "The request is invalid.", {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return _error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Full traceback goes to the (redacted) log; the client gets nothing internal.
        logger.error("Unhandled error", exc_info=exc)
        return _error_response(500, "internal_error", "An unexpected error occurred.")

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(chat.router)
    app.include_router(chat.conversations)
    app.include_router(quizzes.router)
    app.include_router(flashcards.router)
    return app
