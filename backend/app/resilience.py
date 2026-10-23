"""Bounded retries for provider calls."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

from app.errors import AppError, is_openai_error, translate_openai_error

logger = logging.getLogger(__name__)

T = TypeVar("T")


def call_openai(
    fn: Callable[[], T],
    *,
    max_retries: int,
    base_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run `fn`, retrying only transient OpenAI failures (bounded).

    SDK-level retries are disabled on our clients (max_retries=0) so this is the
    only retry layer. Errors that retrying cannot fix (bad key, no credits,
    unknown model) are raised immediately as sanitized AppErrors, which avoids
    burning API calls on hopeless retries.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 - translated or re-raised below
            if not is_openai_error(exc):
                raise
            translated = translate_openai_error(exc)
            if not translated.retryable or attempt >= max_retries:
                logger.warning(
                    "OpenAI call failed (%s) after %d attempt(s)", translated.code, attempt + 1
                )
                raise translated from exc
            delay = base_delay * (2**attempt)
            logger.info("Transient OpenAI error (%s); retrying in %.1fs", translated.code, delay)
            sleep(delay)
            attempt += 1


def invoke_structured(chat_model, schema, system: str, human: str, *, max_retries: int):  # noqa: ANN001
    """One structured-output LLM call, validated against `schema`.

    Raises a sanitized AppError if the provider fails or returns something that
    is not an instance of the schema.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    structured = chat_model.with_structured_output(schema)
    messages = [SystemMessage(content=system), HumanMessage(content=human)]
    try:
        result = call_openai(lambda: structured.invoke(messages), max_retries=max_retries)
    except AppError:
        raise
    except Exception as exc:
        logger.exception("Structured output call failed (%s)", schema.__name__)
        raise AppError(
            "The model returned an unusable response. Please try again.",
            status_code=502, code="invalid_model_output",
        ) from exc
    if not isinstance(result, schema):
        raise AppError(
            "The model returned an unusable response. Please try again.",
            status_code=502, code="invalid_model_output",
        )
    return result


def stream_text(
    chat_model,  # noqa: ANN001
    messages: list,
    *,
    on_token: Callable[[str], None],
    max_retries: int,
    base_delay: float = 1.0,
) -> str:
    """Stream a plain-text completion, forwarding tokens to `on_token`.

    Retries are only allowed while nothing has been emitted yet; once the
    student has seen tokens, a retry would duplicate text, so the error is raised.
    """
    attempt = 0
    while True:
        parts: list[str] = []
        try:
            for chunk in chat_model.stream(messages):
                text = chunk.content if isinstance(chunk.content, str) else ""
                if text:
                    parts.append(text)
                    on_token(text)
            return "".join(parts)
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            if not is_openai_error(exc):
                raise
            translated = translate_openai_error(exc)
            if parts or not translated.retryable or attempt >= max_retries:
                raise translated from exc
            time.sleep(base_delay * (2**attempt))
            attempt += 1
