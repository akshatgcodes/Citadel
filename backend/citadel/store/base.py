"""Storage interface plus an in-memory implementation.

The retriever depends only on `ChunkStore`, so tests (and quick experiments) run on
`InMemoryStore` without a database, while the app uses `PgVectorStore`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import numpy as np

from citadel.models import Chunk


class ChunkStore(Protocol):
    """Minimal operations the pipeline and retriever need."""

    def upsert(self, collection: str, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        """Insert or replace chunks and their embeddings."""
        ...

    def delete_collection(self, collection: str) -> None:
        """Remove every chunk in a collection."""
        ...

    def all_chunks(self, collection: str) -> list[Chunk]:
        """Every chunk in a collection (used to build the BM25 index)."""
        ...

    def vector_search(
        self, collection: str, query: np.ndarray, k: int
    ) -> list[tuple[Chunk, float]]:
        """Top-k chunks by cosine similarity, highest first."""
        ...


class InMemoryStore:
    """Brute-force cosine search over numpy arrays. Fine for thousands of chunks."""

    def __init__(self) -> None:
        self._chunks: dict[str, dict[str, Chunk]] = {}
        self._vectors: dict[str, dict[str, np.ndarray]] = {}

    def upsert(self, collection: str, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        store = self._chunks.setdefault(collection, {})
        vectors = self._vectors.setdefault(collection, {})
        for chunk, vec in zip(chunks, embeddings, strict=True):
            store[chunk.chunk_id] = chunk
            vectors[chunk.chunk_id] = np.asarray(vec, dtype=np.float32)

    def delete_collection(self, collection: str) -> None:
        self._chunks.pop(collection, None)
        self._vectors.pop(collection, None)

    def all_chunks(self, collection: str) -> list[Chunk]:
        return list(self._chunks.get(collection, {}).values())

    def vector_search(
        self, collection: str, query: np.ndarray, k: int
    ) -> list[tuple[Chunk, float]]:
        ids = list(self._vectors.get(collection, {}))
        if not ids:
            return []
        matrix = np.stack([self._vectors[collection][i] for i in ids])
        scores = matrix @ query
        order = np.argsort(-scores)[:k]
        return [(self._chunks[collection][ids[i]], float(scores[i])) for i in order]


class LocalStore(InMemoryStore):
    """`InMemoryStore` persisted to ``<root>/<collection>/{store_chunks.jsonl,vectors.npy}``.

    Useful without a database (and for fast experiment runs): ingest once, query from any
    process.
    """

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root

    def _paths(self, collection: str) -> tuple[Path, Path]:
        base = self.root / collection
        return base / "store_chunks.jsonl", base / "vectors.npy"

    def _load(self, collection: str) -> None:
        if collection in self._chunks:
            return
        chunks_path, vectors_path = self._paths(collection)
        if not chunks_path.exists():
            return
        chunks = [Chunk.model_validate_json(line) for line in chunks_path.read_text().splitlines()]
        super().upsert(collection, chunks, np.load(vectors_path))

    def _save(self, collection: str) -> None:
        chunks_path, vectors_path = self._paths(collection)
        chunks_path.parent.mkdir(parents=True, exist_ok=True)
        ids = list(self._chunks.get(collection, {}))
        chunks_path.write_text(
            "".join(json.dumps(self._chunks[collection][i].model_dump()) + "\n" for i in ids)
        )
        vectors = [self._vectors[collection][i] for i in ids]
        np.save(vectors_path, np.stack(vectors) if vectors else np.zeros((0, 0), np.float32))

    def upsert(self, collection: str, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        self._load(collection)
        super().upsert(collection, chunks, embeddings)
        self._save(collection)

    def delete_collection(self, collection: str) -> None:
        super().delete_collection(collection)
        for path in self._paths(collection):
            path.unlink(missing_ok=True)

    def all_chunks(self, collection: str) -> list[Chunk]:
        self._load(collection)
        return super().all_chunks(collection)

    def vector_search(
        self, collection: str, query: np.ndarray, k: int
    ) -> list[tuple[Chunk, float]]:
        self._load(collection)
        return super().vector_search(collection, query, k)
