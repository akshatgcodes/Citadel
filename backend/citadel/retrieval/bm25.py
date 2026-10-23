"""In-memory BM25 keyword index.

Postgres full-text search ranks with `ts_rank`, which is not BM25 (no IDF weighting or
document-length normalisation). The corpus is a few thousand chunks at most, so building
a real BM25 index in memory at startup takes milliseconds.
"""

from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi

from citadel.models import Chunk

TOKEN = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i if in is it its of on or "
    "shall should that the their there these this to was what when where which who will with "
    "would you your".split()
)


def tokenize(text: str) -> list[str]:
    """Lower-case word tokens, keeping codes like ``21css201t`` and ``3.2`` intact."""
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


class BM25Index:
    """BM25 over a fixed list of chunks."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        corpus = [tokenize(c.embedding_text()) for c in chunks]
        self._bm25 = BM25Okapi(corpus) if chunks else None

    def search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        """Top-k chunks by BM25 score (chunks with zero score are dropped)."""
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        order = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in order if scores[i] > 0]
