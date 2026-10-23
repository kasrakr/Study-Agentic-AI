"""Build validated citations from answer text.

Citations are constructed only from retrieved metadata (documents) and actual
search results (web), keyed by the markers D1/W1. Anything the model writes
that doesn't match a real source is dropped, so a citation can never contain a
model-invented filename, page or URL.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.chat import Citation

SNIPPET_CHARS = 300
# Optional single leading space is consumed so removing a marker leaves no double space.
_GROUP = re.compile(r"(\s?)\[\s*([DW]\d+(?:\s*[,;]\s*[DW]\d+)*)\s*\]")


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= SNIPPET_CHARS else text[:SNIPPET_CHARS].rstrip() + "…"


def build_citations(
    document_sources: list[dict[str, Any]],
    web_sources: list[dict[str, Any]],
    answer_text: str,
) -> tuple[list[Citation], str, str]:
    """Return (citations, cleaned_answer, origin).

    Markers in the text are normalised to separate brackets ([D1, W2] -> [D1][W2])
    and unknown markers are removed.
    """
    docs = {d["marker"]: d for d in document_sources}
    web = {w["marker"]: w for w in web_sources}
    valid = {**docs, **web}
    cited: list[str] = []

    def rewrite(match: re.Match[str]) -> str:
        keep = []
        for raw in re.split(r"[,;]", match.group(2)):
            marker = raw.strip()
            if marker in valid:
                keep.append(marker)
                if marker not in cited:
                    cited.append(marker)
        return match.group(1) + "".join(f"[{m}]" for m in keep) if keep else ""

    cleaned = _GROUP.sub(rewrite, answer_text)

    citations: list[Citation] = []
    for marker in cited:
        if marker in docs:
            d = docs[marker]
            citations.append(Citation(
                source_type="document", marker=marker, snippet=_snippet(d["text"]), score=d.get("score"),
                document_id=d["document_id"], filename=d["filename"],
                page_number=d.get("page_number"), chunk_id=d["chunk_id"],
            ))
        else:
            w = web[marker]
            citations.append(Citation(
                source_type="web", marker=marker, snippet=_snippet(w["content"]), score=w.get("score"),
                title=w["title"], url=w["url"],
            ))

    has_doc = any(c.source_type == "document" for c in citations)
    has_web = any(c.source_type == "web" for c in citations)
    origin = "documents_and_web" if has_doc and has_web else "documents" if has_doc else "web" if has_web else "none"
    return citations, cleaned, origin
