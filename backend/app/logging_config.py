"""Logging setup with secret redaction."""

from __future__ import annotations

import logging
import re

from app.config import Settings

# Matches OpenAI-style (sk-...) and Tavily-style (tvly-...) keys.
_KEY_PATTERN = re.compile(r"\b(?:sk|tvly)-[A-Za-z0-9_\-*]{6,}")


class RedactSecretsFilter(logging.Filter):
    """Scrub API keys from log records, including exception text."""

    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self._secrets = [s for s in secrets if s and len(s) >= 6]

    def _scrub(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "[REDACTED]")
        return _KEY_PATTERN.sub("[REDACTED]", text)

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._scrub(record.getMessage())
        record.args = None
        if record.exc_info:
            # Render the traceback ourselves so we can scrub it too.
            record.exc_text = self._scrub(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def configure_logging(settings: Settings) -> None:
    secrets = [
        s.get_secret_value()
        for s in (settings.openai_api_key, settings.tavily_api_key)
        if s is not None
    ]
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )
    handler.addFilter(RedactSecretsFilter(secrets))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    # Third-party HTTP clients log full URLs/headers at DEBUG; keep them quiet.
    for noisy in ("httpx", "httpcore", "openai", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
