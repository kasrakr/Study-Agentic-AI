"""Centralized configuration.

All settings come from environment variables (or backend/.env). Nothing else in
the codebase should read os.environ directly, and model names are defined only
here so they are never hardcoded across modules.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"

SQLITE_PREFIX = "sqlite:///"


class ConfigurationError(RuntimeError):
    """Raised at startup when required configuration is missing or invalid."""


def _resolve(path_str: str) -> Path:
    """Resolve a possibly-relative path against the repository root."""
    path = Path(path_str).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- OpenAI (default and only implemented provider) ---
    openai_api_key: SecretStr | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout_seconds: float = Field(60.0, gt=0)
    openai_max_retries: int = Field(2, ge=0, le=5)

    # --- Tavily web search (separate key; never the OpenAI key) ---
    tavily_api_key: SecretStr | None = None
    tavily_max_results: int = Field(5, ge=1, le=10)
    tavily_timeout_seconds: float = Field(10.0, gt=0)

    # --- Storage ---
    database_url: str = "sqlite:///storage/study.db"
    chroma_persist_directory: str = "storage/vectorstore"
    upload_directory: str = "storage/uploads"
    chroma_collection_name: str = "study_documents"
    checkpoint_database: str = "storage/checkpoints.sqlite"  # LangGraph conversation state

    # --- API / ingestion ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_size_mb: int = Field(25, ge=1, le=500)
    max_document_pages: int = Field(500, ge=1)
    chunk_size: int = Field(1000, ge=100)
    chunk_overlap: int = Field(150, ge=0)
    embedding_batch_size: int = Field(64, ge=1, le=512)

    # --- Retrieval ---
    retrieval_top_k: int = Field(6, ge=1, le=30)
    retrieval_min_score: float = Field(0.0, ge=0.0, le=1.0)
    # Top similarity below this is a "weak retrieval" signal that triggers a query rewrite.
    retrieval_weak_score: float = Field(0.25, ge=0.0, le=1.0)
    max_retrieval_retries: int = Field(1, ge=0, le=2)  # query rewrites per question
    agent_history_messages: int = Field(6, ge=0, le=20)  # prior messages given to the classifier

    # --- Quizzes / flashcards ---
    quiz_max_questions: int = Field(20, ge=1, le=50)
    flashcard_max_cards: int = Field(30, ge=1, le=100)
    generation_context_chunks: int = Field(24, ge=4, le=80)  # passages sampled per generation

    log_level: str = "INFO"

    @field_validator("openai_api_key", "tavily_api_key", mode="before")
    @classmethod
    def _blank_secret_is_none(cls, value: object) -> object:
        # `OPENAI_API_KEY=` in a .env file should count as "not set".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    # --- Derived values ---
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def checkpoint_path(self) -> Path:
        return _resolve(self.checkpoint_database)

    @property
    def upload_path(self) -> Path:
        return _resolve(self.upload_directory)

    @property
    def chroma_path(self) -> Path:
        return _resolve(self.chroma_persist_directory)

    @property
    def sqlalchemy_url(self) -> str:
        """Database URL with relative SQLite paths anchored at the repo root."""
        if self.database_url.startswith(SQLITE_PREFIX):
            raw = self.database_url[len(SQLITE_PREFIX) :]
            if raw and raw != ":memory:" and not raw.startswith("/"):
                return f"{SQLITE_PREFIX}{_resolve(raw)}"
        return self.database_url

    @property
    def openai_configured(self) -> bool:
        return self.openai_api_key is not None

    @property
    def tavily_configured(self) -> bool:
        return self.tavily_api_key is not None

    def validate_for_startup(self) -> None:
        """Fail fast with a clear message instead of failing on the first request."""
        problems: list[str] = []
        if not self.openai_configured:
            problems.append(
                "OPENAI_API_KEY is not set. Copy backend/.env.example to backend/.env "
                "and add a key from https://platform.openai.com/api-keys"
            )
        if not self.openai_chat_model.strip():
            problems.append("OPENAI_CHAT_MODEL must not be empty.")
        if not self.openai_embedding_model.strip():
            problems.append("OPENAI_EMBEDDING_MODEL must not be empty.")
        if self.chunk_overlap >= self.chunk_size:
            problems.append("CHUNK_OVERLAP must be smaller than CHUNK_SIZE.")
        if problems:
            raise ConfigurationError("Invalid configuration:\n- " + "\n- ".join(problems))

    def ensure_directories(self) -> None:
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        if self.sqlalchemy_url.startswith(SQLITE_PREFIX):
            raw = self.sqlalchemy_url[len(SQLITE_PREFIX) :]
            if raw and raw != ":memory:":
                Path(raw).parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
