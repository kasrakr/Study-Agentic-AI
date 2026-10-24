"""Pure metric functions. No model or network access, so they are easy to test."""

from __future__ import annotations

import re
import statistics
from typing import Any


def retrieval_outcome(retrieved_filenames: list[str], expected: list[str]) -> dict[str, Any] | None:
    """Did the expected document(s) appear in the retrieved passages, and how high?

    Returns None when the question has no expected document (nothing to measure).
    """
    if not expected:
        return None
    rank = next((i for i, f in enumerate(retrieved_filenames, start=1) if f in expected), None)
    return {"hit": rank is not None, "rank": rank, "reciprocal_rank": 1 / rank if rank else 0.0}


def web_decision(needs_web: bool, web_used: bool) -> str:
    if needs_web:
        return "correct_use" if web_used else "missed_web"
    return "unnecessary_web" if web_used else "correct_avoid"


def _norm(text: str) -> str:
    return " ".join(text.split())


def check_citations(
    citations: list[dict[str, Any]],
    *,
    expected_documents: list[str],
    stored_chunks: dict[str, tuple[str, dict]],
    web_urls_returned: set[str],
) -> dict[str, Any]:
    """Deterministic citation correctness.

    A document citation is valid if its chunk exists in the index with the same file/document id and the
    quoted snippet really is the start of that chunk. A web citation is valid only if its URL was actually
    returned by the search provider for this question.
    """
    invalid: list[str] = []
    cited_files: list[str] = []
    for c in citations:
        if c["source_type"] == "document":
            stored = stored_chunks.get(c["chunk_id"])
            snippet = _norm(c["snippet"]).rstrip("…").rstrip()
            if stored is None:
                invalid.append(f'{c["marker"]}: chunk not found')
            elif stored[1].get("filename") != c["filename"] or stored[1].get("document_id") != c["document_id"]:
                invalid.append(f'{c["marker"]}: metadata mismatch')
            elif not _norm(stored[0]).startswith(snippet):
                invalid.append(f'{c["marker"]}: snippet is not from the chunk')
            else:
                cited_files.append(c["filename"])
        elif c.get("url") not in web_urls_returned:
            invalid.append(f'{c["marker"]}: URL was not returned by web search')
    unexpected = sorted({f for f in cited_files if expected_documents and f not in expected_documents})
    return {
        "citations": len(citations),
        "valid": not invalid,
        "invalid": invalid,
        "cites_expected": (any(f in expected_documents for f in cited_files) if expected_documents else None),
        "unexpected_documents": unexpected,
    }


def _rate(values: list[bool]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    retrieval = [r["retrieval"] for r in results if r.get("retrieval")]
    judged = [r["judge"] for r in results if r.get("judge")]
    cited = [r["citation_check"] for r in results if r.get("citation_check") and r["citation_check"]["citations"] > 0]
    expected_rates = [c["cites_expected"] for c in cited if c["cites_expected"] is not None]
    web = [r["web_decision"] for r in results if r.get("web_decision")]
    latencies = sorted(r["latency_ms"] for r in results if r.get("latency_ms") is not None)
    facts = [x for j in judged for x in j.get("key_facts_covered", [])]
    usage = [r["usage"] for r in results if r.get("usage")]

    def total(key: str) -> int | None:
        return sum(u.get(key, 0) for u in usage) if usage else None

    return {
        "questions": len(results),
        "retrieval": {"evaluated": len(retrieval), "hit_rate": _rate([r["hit"] for r in retrieval]),
                      "mrr": round(statistics.fmean(r["reciprocal_rank"] for r in retrieval), 3) if retrieval else None},
        "faithfulness": {"judged": len(judged), "all_claims_supported_rate": _rate([j["all_claims_supported"] for j in judged]),
                         "key_fact_recall": _rate(facts), "note": "Judged by an LLM; treat as an estimate."},
        "citations": {"answers_with_citations": len(cited), "valid_rate": _rate([c["valid"] for c in cited]),
                      "cites_expected_document_rate": _rate(expected_rates)},
        "web_search": {**{k: web.count(k) for k in ("correct_use", "correct_avoid", "missed_web", "unnecessary_web")},
                       "decision_accuracy": _rate([w in ("correct_use", "correct_avoid") for w in web])},
        "latency_ms": {"mean": round(statistics.fmean(latencies)) if latencies else None,
                       "median": round(statistics.median(latencies)) if latencies else None,
                       "max": latencies[-1] if latencies else None},
        "token_usage": {"input": total("input_tokens"), "output": total("output_tokens"), "total": total("total_tokens"),
                        "note": "Only counted when the provider reports usage."},
    }


def compare_modes(per_mode: dict[str, list[dict[str, Any] | None]]) -> dict[str, Any]:
    out = {}
    for mode, rows in per_mode.items():
        rows = [r for r in rows if r]
        out[mode] = {"evaluated": len(rows), "hit_rate": _rate([r["hit"] for r in rows]),
                     "mrr": round(statistics.fmean(r["reciprocal_rank"] for r in rows), 3) if rows else None}
    return out
