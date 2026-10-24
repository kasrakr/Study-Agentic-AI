"""Small BM25 implementation for keyword matching (exact terms, identifiers, equations).

Tokens are lowercase alphanumeric runs, so "XJ-4471" becomes ["xj", "4471"] and "E=mc2" becomes
["e", "mc2"]. That is crude but makes rare identifiers and symbols dominate through IDF.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25:
    def __init__(self, documents: list[list[str]], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.n = len(documents)
        self.lengths = [len(d) for d in documents]
        self.avg_len = (sum(self.lengths) / self.n) if self.n else 0.0
        self.term_freqs = [Counter(d) for d in documents]
        df: Counter[str] = Counter()
        for tf in self.term_freqs:
            df.update(tf.keys())
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def top(self, query_tokens: list[str], k: int) -> list[tuple[int, float]]:
        """Return (document index, score) for the best matches; documents with no query term are omitted."""
        terms = [t for t in dict.fromkeys(query_tokens) if t in self.idf]
        scored: list[tuple[int, float]] = []
        for i, tf in enumerate(self.term_freqs):
            score = 0.0
            norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / (self.avg_len or 1.0))
            for t in terms:
                f = tf.get(t, 0)
                if f:
                    score += self.idf[t] * f * (self.k1 + 1) / (f + norm)
            if score > 0:
                scored.append((i, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


def reciprocal_rank_fusion(rankings: list[list[str]], *, k: int = 60) -> dict[str, float]:
    """Fuse ranked id lists: score(id) = sum over lists of 1 / (k + rank), rank starting at 1."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            fused[item] = fused.get(item, 0.0) + 1.0 / (k + rank)
    return fused
