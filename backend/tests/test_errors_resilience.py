import logging

import httpx
import openai
import pytest

from app.errors import AppError, translate_openai_error
from app.logging_config import RedactSecretsFilter
from app.resilience import call_openai


def _resp(status: int) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", "https://api.openai.com/v1/x"))


def auth_error():
    return openai.AuthenticationError("Incorrect API key provided: sk-abc123SECRET", response=_resp(401), body=None)


def quota_error():
    return openai.RateLimitError("quota", response=_resp(429), body={"code": "insufficient_quota"})


def rate_error():
    return openai.RateLimitError("slow down", response=_resp(429), body={"code": "rate_limit_exceeded"})


def test_translation_is_sanitized_and_classified():
    auth = translate_openai_error(auth_error())
    assert auth.code == "openai_auth_failed" and not auth.retryable
    assert "sk-abc123SECRET" not in auth.message

    quota = translate_openai_error(quota_error())
    assert quota.code == "openai_insufficient_quota" and not quota.retryable
    assert "ChatGPT subscription" in quota.message

    assert translate_openai_error(rate_error()).retryable
    timeout = translate_openai_error(openai.APITimeoutError(request=httpx.Request("POST", "https://x")))
    assert timeout.code == "openai_timeout" and timeout.retryable


def test_transient_error_is_retried_then_succeeds():
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise rate_error()
        return "ok"

    assert call_openai(flaky, max_retries=2) == "ok"
    assert len(attempts) == 3


def test_retries_are_bounded():
    attempts = []

    def always_rate_limited():
        attempts.append(1)
        raise rate_error()

    with pytest.raises(AppError) as info:
        call_openai(always_rate_limited, max_retries=2)
    assert info.value.code == "openai_rate_limited"
    assert len(attempts) == 3  # 1 try + 2 retries


@pytest.mark.parametrize("make_error", [auth_error, quota_error])
def test_unrecoverable_errors_are_not_retried(make_error):
    attempts = []

    def failing():
        attempts.append(1)
        raise make_error()

    with pytest.raises(AppError):
        call_openai(failing, max_retries=5)
    assert len(attempts) == 1


def test_non_openai_exceptions_pass_through_untouched():
    with pytest.raises(ValueError):
        call_openai(lambda: (_ for _ in ()).throw(ValueError("boom")), max_retries=3)


def test_log_filter_redacts_keys_in_messages_and_tracebacks():
    f = RedactSecretsFilter(["my-exact-secret-value"])
    try:
        raise RuntimeError("failed with sk-proj-abcdef123456 and my-exact-secret-value")
    except RuntimeError:
        import sys
        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "key=%s", ("sk-live-abcdef123456",), sys.exc_info())
    f.filter(record)
    text = record.msg + (record.exc_text or "")
    assert "abcdef123456" not in text and "my-exact-secret-value" not in text
    assert "[REDACTED]" in text
