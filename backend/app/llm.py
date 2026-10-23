"""Centralized chat-model initialization (OpenAI only, by design).

Every LLM call in the app obtains its model from `get_chat_model` so the model
name, timeout and key handling live in exactly one place. The SDK's own retry
layer is disabled (max_retries=0); bounded retries are handled by
`app.resilience.call_openai`.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config import Settings, ConfigurationError

# Reasoning-model families reject non-default `temperature`; omit it for them.
_NO_TEMPERATURE_PREFIXES = ("o1", "o3", "o4", "gpt-5")


def get_chat_model(settings: Settings, *, temperature: float = 0.0) -> ChatOpenAI:
    """Build a ChatOpenAI client.

    Use temperature=0 for grounded answering, grading and classification, and a
    modest value (e.g. 0.4) only for creative generation such as quizzes.
    """
    if settings.openai_api_key is None:
        raise ConfigurationError("OPENAI_API_KEY is not set.")
    kwargs: dict[str, object] = {}
    if not settings.openai_chat_model.lower().startswith(_NO_TEMPERATURE_PREFIXES):
        kwargs["temperature"] = temperature
    return ChatOpenAI(
        model=settings.openai_chat_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=settings.openai_timeout_seconds,
        max_retries=0,
        **kwargs,
    )
