import httpx
import pytest
from pydantic import SecretStr

from app.services.web_search import MAX_CONTENT_CHARS, TavilySearch, WebSearchError

KEY = "tvly-secret-key-123456"


def make(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return TavilySearch(SecretStr(KEY), client=client)


def ok(results):
    return lambda request: httpx.Response(200, json={"results": results})


def test_parses_results_and_sends_key_only_in_auth_header():
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"results": [
            {"title": "T", "url": "https://a.edu/x", "content": "Body", "score": 0.8, "published_date": "2026-01-01"}]})

    results = make(handler).search("osmosis definition", max_results=5)
    assert seen["auth"] == f"Bearer {KEY}" and KEY not in seen["body"]
    assert '"max_results":5' in seen["body"].replace(" ", "")
    assert (results[0].title, results[0].url, results[0].score) == ("T", "https://a.edu/x", 0.8)


def test_filters_bad_entries_dedupes_and_limits():
    rows = [
        {"title": "A", "url": "https://a.test/1", "content": "x" * 5000},
        {"title": "dup", "url": "https://a.test/1", "content": "same url"},
        {"title": "no content", "url": "https://b.test", "content": "  "},
        {"title": "bad scheme", "url": "javascript:alert(1)", "content": "x"},
        {"title": "ftp", "url": "ftp://c.test", "content": "x"},
        "garbage",
        {"title": "B", "url": "https://d.test", "content": "ok"},
        {"title": "C", "url": "https://e.test", "content": "ok"},
    ]
    results = make(ok(rows)).search("q", max_results=2)
    assert [r.title for r in results] == ["A", "B"]
    assert len(results[0].content) == MAX_CONTENT_CHARS


def test_empty_results_return_empty_list():
    assert make(ok([])).search("q", max_results=5) == []


@pytest.mark.parametrize("status,code", [(401, "web_search_auth_failed"), (403, "web_search_auth_failed"),
                                         (429, "web_search_rate_limited"), (500, "web_search_failed")])
def test_http_errors_become_sanitized_errors(status, code):
    with pytest.raises(WebSearchError) as info:
        make(lambda r: httpx.Response(status, text=f"upstream said {KEY}")).search("q", max_results=3)
    assert info.value.code == code and KEY not in info.value.message


def test_timeout_and_connection_errors():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request):
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(WebSearchError) as t:
        make(timeout).search("q", max_results=3)
    assert t.value.code == "web_search_timeout"
    with pytest.raises(WebSearchError) as c:
        make(refused).search("q", max_results=3)
    assert c.value.code == "web_search_unreachable"


def test_unreadable_response_and_long_queries():
    with pytest.raises(WebSearchError):
        make(lambda r: httpx.Response(200, text="<html>not json</html>")).search("q", max_results=3)
    sent = {}
    make(lambda r: (sent.update(body=r.content.decode()) or httpx.Response(200, json={"results": []}))).search("q" * 1000, max_results=3)
    assert sent["body"].count("q") <= 400
    with pytest.raises(WebSearchError):
        make(ok([])).search("   ", max_results=3)
