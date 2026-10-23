"""Retrieval on a toy corpus: BM25, RRF fusion, hybrid search and re-ranking.

Uses `InMemoryStore` and a deterministic bag-of-words "embedder", so no models or
database are needed.
"""

from __future__ import annotations

import numpy as np
import pytest

from citadel.models import Chunk
from citadel.retrieval.bm25 import BM25Index, tokenize
from citadel.retrieval.fusion import reciprocal_rank_fusion
from citadel.retrieval.retriever import Retriever
from citadel.store.base import InMemoryStore

COLLECTION = "test"

CORPUS = {
    "att": "Students must maintain a minimum of 75% attendance in each course to sit the exam.",
    "fee": "The tuition fee must be paid before the start of each semester; late payment incurs a fine.",
    "os": "21CSC202J Operating Systems carries 4 credits: 3 lecture hours and 2 practical hours.",
    "rag": "Ragging in any form is a Level 6 misconduct and leads to expulsion from the university.",
    "lib": "Library books may be borrowed for fourteen days and renewed once.",
}


class BagOfWordsEmbedder:
    """Hashes tokens into a fixed-size normalised vector. Shared words = similar vectors."""

    dim = 64

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in tokenize(text):
            v[sum(map(ord, tok)) % self.dim] += 1
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_query(self, query: str) -> np.ndarray:
        return self._vec(query)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts])


def make_chunk(cid: str, text: str) -> Chunk:
    return Chunk(chunk_id=cid, doc_id="handbook", doc_title="Student Handbook", page=1, text=text)


@pytest.fixture
def retriever() -> Retriever:
    chunks = [make_chunk(cid, text) for cid, text in CORPUS.items()]
    embedder = BagOfWordsEmbedder()
    store = InMemoryStore()
    store.upsert(COLLECTION, chunks, embedder.embed_passages([c.embedding_text() for c in chunks]))
    return Retriever(store, COLLECTION, embedder)


def test_tokenize_keeps_course_codes_and_drops_stopwords() -> None:
    assert tokenize("What are the credits for 21CSC202J?") == ["credits", "21csc202j"]


def test_bm25_exact_code_match() -> None:
    index = BM25Index([make_chunk(cid, text) for cid, text in CORPUS.items()])
    hits = index.search("21CSC202J", k=3)
    assert hits[0][0].chunk_id == "os"
    assert len(hits) == 1  # zero-score chunks are dropped


def test_rrf_rewards_agreement() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]], k=60)
    ids = [i for i, _ in fused]
    assert set(ids[:2]) == {"a", "b"}  # in both lists near the top
    assert ids[-1] in {"c", "d"}
    assert fused[0][1] == pytest.approx(1 / 61 + 1 / 62)


def test_rrf_single_list_preserves_order() -> None:
    assert [i for i, _ in reciprocal_rank_fusion([["x", "y", "z"]])] == ["x", "y", "z"]


@pytest.mark.parametrize("mode", ["vector", "bm25", "hybrid"])
def test_each_mode_finds_attendance_rule(retriever: Retriever, mode: str) -> None:
    result = retriever.retrieve("minimum attendance percentage", k=2, mode=mode)  # type: ignore[arg-type]
    assert result.chunks[0].chunk.chunk_id == "att"
    assert len(result.chunks) <= 2


def test_hybrid_records_component_scores(retriever: Retriever) -> None:
    top = retriever.retrieve("ragging misconduct", k=1, mode="hybrid").chunks[0]
    assert top.chunk.chunk_id == "rag"
    assert top.vector_rank is not None and top.bm25_rank is not None
    assert top.rrf_score == top.score


def test_timings_reported(retriever: Retriever) -> None:
    result = retriever.retrieve("library", k=1, mode="hybrid")
    assert {"vector_ms", "bm25_ms", "total_ms"} <= result.timings_ms.keys()


class PreferFees:
    """Fake cross-encoder that scores passages mentioning fees highest."""

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [1.0 if "fee" in p else 0.0 for p in passages]


def test_rerank_reorders_candidates() -> None:
    chunks = [make_chunk(cid, text) for cid, text in CORPUS.items()]
    embedder = BagOfWordsEmbedder()
    store = InMemoryStore()
    store.upsert(COLLECTION, chunks, embedder.embed_passages([c.embedding_text() for c in chunks]))
    r = Retriever(store, COLLECTION, embedder, reranker_factory=PreferFees)
    result = r.retrieve("semester", k=2, mode="hybrid", rerank=True)
    assert result.chunks[0].chunk.chunk_id == "fee"
    assert result.chunks[0].rerank_score == 1.0
    assert "rerank_ms" in result.timings_ms


def test_rerank_without_reranker_raises(retriever: Retriever) -> None:
    with pytest.raises(RuntimeError):
        retriever.retrieve("fees", rerank=True)
