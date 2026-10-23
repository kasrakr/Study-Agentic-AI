"""Embedding model initialization (OpenAI only, by design).

Stored vectors and query vectors must come from the same model. The vector
index records the model name in the Chroma collection metadata and refuses to
open a collection built with a different one (see rag/indexer.py).
"""

from __future__ import annotations

from langchain_openai import OpenAIEmbeddings

from app.config import ConfigurationError, Settings


def get_embeddings(settings: Settings) -> OpenAIEmbeddings:
    if settings.openai_api_key is None:
        raise ConfigurationError("OPENAI_API_KEY is not set.")
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        request_timeout=settings.openai_timeout_seconds,
        max_retries=0,
        # Chunks are a few hundred tokens, far below the model's input limit, so
        # the client-side token-length check is unnecessary. Disabling it also
        # avoids tiktoken downloading its vocabulary from a second host at runtime.
        check_embedding_ctx_length=False,
    )
