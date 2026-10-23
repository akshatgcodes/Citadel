"""Central configuration. Every tunable comes from the environment (or `.env`)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RetrievalMode = Literal["vector", "bm25", "hybrid"]


class Settings(BaseSettings):
    """Runtime settings. Field names map to upper-case env vars (e.g. CHUNK_SIZE)."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Paths
    raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    manifest_path: Path = PROJECT_ROOT / "data" / "manifest.yaml"

    # Storage: "pgvector" (Postgres) or "local" (numpy files under data/processed/)
    vector_store: Literal["pgvector", "local"] = "pgvector"
    database_url: str = "postgresql://localhost:5432/citadel"

    # Ingestion
    chunk_size: int = 400  # tokens, measured with the embedding model's tokenizer
    chunk_overlap: int = 60  # tokens
    ocr_dpi: int = 300
    ocr_language: str = "eng"

    # Embeddings / re-ranking
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_query_prefix: str = "Represent this sentence for searching relevant passages: "
    embed_batch_size: int = 32
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Retrieval
    top_k: int = 5
    retrieval_mode: RetrievalMode = "hybrid"
    rerank: bool = False
    rerank_candidates: int = 20  # how many fused candidates the cross-encoder re-scores
    rrf_k: int = 60

    # Generation (Phase 2)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    @property
    def collection(self) -> str:
        """Name of the chunk collection for the current embedding + chunking config.

        Each (model, chunk size, overlap) combination is stored separately so experiments
        can compare configs without re-ingesting the others.
        """
        model = self.embed_model.split("/")[-1].lower()
        return f"{model}__cs{self.chunk_size}_ov{self.chunk_overlap}"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings object."""
    return Settings()
