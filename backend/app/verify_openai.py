"""CLI check:  python -m app.verify_openai   (run from the backend directory)."""

from __future__ import annotations

import sys

from app.config import ConfigurationError, get_settings
from app.llm import get_chat_model
from app.rag.embeddings import get_embeddings
from app.services.openai_check import verify_openai


def main() -> int:
    settings = get_settings()
    try:
        settings.validate_for_startup()
    except ConfigurationError as exc:
        print(exc)
        return 1
    result = verify_openai(settings, get_embeddings(settings), get_chat_model(settings))
    for name in ("embedding", "chat"):
        item = result[name]
        status = "OK" if item["ok"] else f"FAILED - {item['error']['message']}"
        print(f"{name:<10} {item['model']:<28} {status}")
    return 0 if all(result[n]["ok"] for n in ("embedding", "chat")) else 1


if __name__ == "__main__":
    sys.exit(main())
