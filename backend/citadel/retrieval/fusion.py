"""Reciprocal Rank Fusion (Cormack et al., 2009).

Vector similarity (0..1) and BM25 (unbounded) live on different scales, so adding them
needs fragile normalisation. RRF uses ranks only: score(d) = sum over lists of 1/(k + rank).
k=60 is the standard value; it damps the advantage of being ranked first in one list.
"""

from __future__ import annotations

from collections.abc import Sequence


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], k: int = 60
) -> list[tuple[str, float]]:
    """Fuse ranked id lists into one ranking.

    Args:
        rankings: each inner sequence is ids ordered best-first.
        k: RRF damping constant.

    Returns:
        ``(id, rrf_score)`` pairs, highest score first. Ties keep first-seen order.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
