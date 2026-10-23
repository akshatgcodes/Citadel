"""Cross-encoder re-ranking.

A bi-encoder embeds query and chunk separately; a cross-encoder reads them together and
scores relevance directly, which is more accurate but too slow to run over the whole
corpus. So it only re-scores the top candidates from hybrid retrieval.
"""

from __future__ import annotations

from functools import lru_cache


class Reranker:
    """Scores (query, passage) pairs with a sentence-transformers CrossEncoder."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder

        self.model_name = model_name
        self._model = CrossEncoder(model_name)

    def score(self, query: str, passages: list[str]) -> list[float]:
        """Relevance score for each passage (higher is more relevant)."""
        if not passages:
            return []
        return [float(s) for s in self._model.predict([(query, p) for p in passages])]


@lru_cache(maxsize=2)
def get_reranker(model_name: str) -> Reranker:
    """Process-wide cached re-ranker."""
    return Reranker(model_name)
