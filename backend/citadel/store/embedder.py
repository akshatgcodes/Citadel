"""Sentence-transformers embedding wrapper.

Default model: BAAI/bge-small-en-v1.5 (384 dimensions, ~33M parameters). It is among the
strongest small models on the MTEB retrieval benchmark and runs fast on a laptop CPU.
BGE models expect an instruction prefix on queries (not on passages), which is applied here.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np


class Embedder:
    """Encodes passages and queries into L2-normalised vectors (so dot product = cosine)."""

    def __init__(self, model_name: str, query_prefix: str = "", batch_size: int = 32) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.query_prefix = query_prefix
        self.batch_size = batch_size
        self._model = SentenceTransformer(model_name)

    @property
    def dim(self) -> int:
        """Embedding dimensionality."""
        getter = getattr(self._model, "get_embedding_dimension", None) or (
            self._model.get_sentence_embedding_dimension
        )
        return int(getter() or 0)

    def embed_passages(self, texts: list[str], show_progress: bool = False) -> np.ndarray:
        """Embed document chunks."""
        return self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        ).astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a search query (with the model's query instruction prefix)."""
        return self._model.encode(
            [self.query_prefix + query], normalize_embeddings=True, convert_to_numpy=True
        )[0].astype(np.float32)


@lru_cache(maxsize=2)
def get_embedder(model_name: str, query_prefix: str = "", batch_size: int = 32) -> Embedder:
    """Process-wide cached embedder (model loading takes a few seconds)."""
    return Embedder(model_name, query_prefix, batch_size)
