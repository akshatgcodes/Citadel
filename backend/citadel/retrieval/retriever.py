"""Retrieval orchestration: vector, BM25 or hybrid (RRF), with optional re-ranking."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

import numpy as np

from citadel.config import RetrievalMode
from citadel.models import Chunk, RetrievalResult, RetrievedChunk
from citadel.retrieval.bm25 import BM25Index
from citadel.retrieval.fusion import reciprocal_rank_fusion
from citadel.store.base import ChunkStore


class QueryEmbedder(Protocol):
    def embed_query(self, query: str) -> np.ndarray: ...


class Scorer(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]: ...


class Retriever:
    """Finds the chunks most relevant to a question.

    Each first-stage retriever fetches ``candidates`` results (more than ``k``) so fusion
    and re-ranking have something to choose from; the final list is cut to ``k``.
    """

    def __init__(
        self,
        store: ChunkStore,
        collection: str,
        embedder: QueryEmbedder,
        reranker_factory: Callable[[], Scorer] | None = None,
        rrf_k: int = 60,
    ) -> None:
        self.store = store
        self.collection = collection
        self.embedder = embedder
        self._reranker_factory = reranker_factory
        self._reranker: Scorer | None = None
        self.rrf_k = rrf_k
        self.bm25 = BM25Index(store.all_chunks(collection))

    def refresh(self) -> None:
        """Rebuild the BM25 index after the collection changes."""
        self.bm25 = BM25Index(self.store.all_chunks(self.collection))

    @property
    def reranker(self) -> Scorer:
        if self._reranker is None:
            if self._reranker_factory is None:
                raise RuntimeError("re-ranking requested but no reranker configured")
            self._reranker = self._reranker_factory()
        return self._reranker

    def retrieve(
        self,
        query: str,
        k: int = 5,
        mode: RetrievalMode = "hybrid",
        rerank: bool = False,
        candidates: int = 20,
    ) -> RetrievalResult:
        """Return the top-``k`` chunks for ``query`` with per-stage scores and timings."""
        timings: dict[str, float] = {}
        pool = max(candidates, k)
        found: dict[str, RetrievedChunk] = {}

        def entry(chunk: Chunk) -> RetrievedChunk:
            return found.setdefault(chunk.chunk_id, RetrievedChunk(chunk=chunk, score=0.0))

        vector_ids: list[str] = []
        bm25_ids: list[str] = []
        if mode in ("vector", "hybrid"):
            t0 = time.perf_counter()
            qvec = self.embedder.embed_query(query)
            hits = self.store.vector_search(self.collection, qvec, pool)
            timings["vector_ms"] = (time.perf_counter() - t0) * 1000
            for rank, (chunk, score) in enumerate(hits, start=1):
                e = entry(chunk)
                e.vector_score, e.vector_rank, e.score = score, rank, score
                vector_ids.append(chunk.chunk_id)
        if mode in ("bm25", "hybrid"):
            t0 = time.perf_counter()
            hits = self.bm25.search(query, pool)
            timings["bm25_ms"] = (time.perf_counter() - t0) * 1000
            for rank, (chunk, score) in enumerate(hits, start=1):
                e = entry(chunk)
                e.bm25_score, e.bm25_rank = score, rank
                if mode == "bm25":
                    e.score = score
                bm25_ids.append(chunk.chunk_id)

        if mode == "hybrid":
            fused = reciprocal_rank_fusion([vector_ids, bm25_ids], k=self.rrf_k)
            ranked = []
            for cid, rrf in fused:
                found[cid].rrf_score = rrf
                found[cid].score = rrf
                ranked.append(found[cid])
        else:
            order = vector_ids if mode == "vector" else bm25_ids
            ranked = [found[cid] for cid in order]

        ranked = ranked[:pool]
        if rerank and ranked:
            reranker = self.reranker  # load the model outside the timed section
            t0 = time.perf_counter()
            scores = reranker.score(query, [r.chunk.embedding_text() for r in ranked])
            for r, s in zip(ranked, scores, strict=True):
                r.rerank_score = s
                r.score = s
            ranked.sort(key=lambda r: r.score, reverse=True)
            timings["rerank_ms"] = (time.perf_counter() - t0) * 1000

        timings["total_ms"] = sum(timings.values())
        return RetrievalResult(query=query, chunks=ranked[:k], timings_ms=timings)
