"""Application errors and sanitized translation of provider errors.

Client-facing messages never include raw exception text from providers, because
those messages can contain fragments of API keys or internal details.
"""

from __future__ import annotations

import logging
from typing import Any

import openai

logger = logging.getLogger(__name__)


class AppError(Exception):
    """An error that is safe to show to the client."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: str = "bad_request",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}
        self.retryable = retryable


class NotFoundError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=404, code="not_found", details=details)


def translate_openai_error(exc: Exception) -> AppError:
    """Map an OpenAI SDK exception to a sanitized AppError.

    `retryable` is True only for transient failures. Authentication, quota,
    unknown-model and bad-request errors cannot be fixed by retrying.
    """
    if isinstance(exc, openai.AuthenticationError):
        return AppError(
            "OpenAI rejected the API key. Check OPENAI_API_KEY in backend/.env.",
            status_code=502, code="openai_auth_failed",
        )
    if isinstance(exc, openai.PermissionDeniedError):
        return AppError(
            "The OpenAI API key does not have permission for this model or region.",
            status_code=502, code="openai_permission_denied",
        )
    if isinstance(exc, openai.NotFoundError):
        return AppError(
            "The configured OpenAI model was not found or is not available to this "
            "account. Check OPENAI_CHAT_MODEL / OPENAI_EMBEDDING_MODEL.",
            status_code=502, code="openai_model_unavailable",
        )
    if isinstance(exc, openai.RateLimitError):
        if getattr(exc, "code", None) == "insufficient_quota":
            return AppError(
                "The OpenAI account has insufficient API credits. API billing is "
                "separate from a ChatGPT subscription; check your API usage and billing.",
                status_code=402, code="openai_insufficient_quota",
            )
        return AppError(
            "OpenAI rate limit exceeded. Please wait a moment and try again.",
            status_code=429, code="openai_rate_limited", retryable=True,
        )
    if isinstance(exc, openai.APITimeoutError):
        return AppError(
            "The request to OpenAI timed out.",
            status_code=504, code="openai_timeout", retryable=True,
        )
    if isinstance(exc, openai.APIConnectionError):
        return AppError(
            "Could not reach the OpenAI API. Check your network connection.",
            status_code=502, code="openai_connection_error", retryable=True,
        )
    if isinstance(exc, openai.InternalServerError):
        return AppError(
            "OpenAI is temporarily unavailable.",
            status_code=502, code="openai_server_error", retryable=True,
        )
    if isinstance(exc, openai.BadRequestError):
        return AppError(
            "OpenAI rejected the request (for example, input too long or an "
            "unsupported parameter for the configured model).",
            status_code=502, code="openai_bad_request",
        )
    return AppError(
        "Unexpected error while calling OpenAI.",
        status_code=502, code="openai_error",
    )


def is_openai_error(exc: BaseException) -> bool:
    return isinstance(exc, openai.OpenAIError)
