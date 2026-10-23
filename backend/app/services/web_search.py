"""Web search as an independent, replaceable service.

The agent depends only on the `WebSearchProvider` protocol. Tavily is the
initial implementation; another provider can be added without touching the
graph. Search results are untrusted data and are never treated as instructions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

import httpx
from pydantic import SecretStr

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
MAX_QUERY_CHARS = 380  # Tavily rejects very long queries
MAX_CONTENT_CHARS = 1500  # keep prompts small


class WebSearchError(Exception):
    """A sanitized failure. The message is safe to show to the user."""

    def __init__(self, message: str, *, code: str = "web_search_failed") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class WebResult:
    title: str
    url: str
    content: str
    score: float | None = None
    published_date: str | None = None
    extra: dict = field(default_factory=dict)


class WebSearchProvider(Protocol):
    def search(self, query: str, *, max_results: int) -> list[WebResult]: ...


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


class TavilySearch:
    """Tavily Search API client (https://docs.tavily.com)."""

    def __init__(
        self,
        api_key: SecretStr,
        *,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
        url: str = TAVILY_URL,
    ) -> None:
        self._api_key = api_key
        self._url = url
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def search(self, query: str, *, max_results: int) -> list[WebResult]:
        query = query.strip()[:MAX_QUERY_CHARS]
        if not query:
            raise WebSearchError("Empty web search query.", code="web_search_empty_query")
        try:
            response = self._client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                json={
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_images": False,
                },
            )
        except httpx.TimeoutException as exc:
            raise WebSearchError("The web search timed out.", code="web_search_timeout") from exc
        except httpx.HTTPError as exc:
            logger.warning("Tavily connection error: %s", type(exc).__name__)
            raise WebSearchError("Could not reach the web search service.", code="web_search_unreachable") from exc

        if response.status_code in (401, 403):
            raise WebSearchError("The Tavily API key was rejected. Check TAVILY_API_KEY.", code="web_search_auth_failed")
        if response.status_code == 429:
            raise WebSearchError("The web search rate limit or plan quota was reached.", code="web_search_rate_limited")
        if response.status_code >= 400:
            logger.warning("Tavily returned HTTP %s", response.status_code)
            raise WebSearchError(f"The web search service returned an error ({response.status_code}).")

        try:
            raw_results = response.json().get("results", [])
        except ValueError as exc:
            raise WebSearchError("The web search service returned an unreadable response.") from exc

        results: list[WebResult] = []
        seen: set[str] = set()
        for item in raw_results if isinstance(raw_results, list) else []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            content = str(item.get("content") or "").strip()
            if not _is_http_url(url) or not content or url in seen:
                continue
            seen.add(url)
            score = item.get("score")
            results.append(
                WebResult(
                    title=str(item.get("title") or url).strip()[:200],
                    url=url,
                    content=content[:MAX_CONTENT_CHARS],
                    score=float(score) if isinstance(score, (int, float)) else None,
                    published_date=item.get("published_date") if isinstance(item.get("published_date"), str) else None,
                )
            )
            if len(results) >= max_results:
                break
        return results
