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
