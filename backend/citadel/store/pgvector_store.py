"""PostgreSQL + pgvector chunk store.

One table per embedding dimension (``chunks_384``, ``chunks_768``) holds every collection
(a collection = one embedding model + chunking config), so experiments can coexist.
Cosine distance with an HNSW index. Because several collections share an index,
pgvector's iterative index scan is enabled so a ``WHERE collection = ...`` filter
still returns a full top-k instead of whatever survived the first index pass.
"""

from __future__ import annotations

import json

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from citadel.models import Chunk

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks_{dim} (
    collection  text    NOT NULL,
    chunk_id    text    NOT NULL,
    doc_id      text    NOT NULL,
    page        integer NOT NULL,
    data        jsonb   NOT NULL,
    embedding   vector({dim}) NOT NULL,
    PRIMARY KEY (collection, chunk_id)
);
CREATE INDEX IF NOT EXISTS chunks_{dim}_hnsw
    ON chunks_{dim} USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_{dim}_collection ON chunks_{dim} (collection);
"""


class PgVectorStore:
    """`ChunkStore` backed by Postgres. Chunk metadata is stored as JSONB."""

    def __init__(self, database_url: str, dim: int) -> None:
        self.database_url = database_url
        self.dim = dim
        self.table = f"chunks_{dim}"
        self._conn: psycopg.Connection | None = None

    @property
    def conn(self) -> psycopg.Connection:
        """Lazily opened autocommit connection with the vector type registered."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self.database_url, autocommit=True)
            self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            register_vector(self._conn)
            self._conn.execute(SCHEMA.format(dim=self.dim))
            self._conn.execute("SET hnsw.iterative_scan = relaxed_order")
        return self._conn

    def upsert(self, collection: str, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        with self.conn.cursor() as cur:
            cur.executemany(
                f"""
                INSERT INTO {self.table} (collection, chunk_id, doc_id, page, data, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (collection, chunk_id) DO UPDATE
                SET doc_id = EXCLUDED.doc_id, page = EXCLUDED.page,
                    data = EXCLUDED.data, embedding = EXCLUDED.embedding
                """,
                [
                    (collection, c.chunk_id, c.doc_id, c.page, json.dumps(c.model_dump()), vec)
                    for c, vec in zip(chunks, embeddings, strict=True)
                ],
            )

    def delete_collection(self, collection: str) -> None:
        self.conn.execute(f"DELETE FROM {self.table} WHERE collection = %s", (collection,))

    def all_chunks(self, collection: str) -> list[Chunk]:
        rows = self.conn.execute(
            f"SELECT data FROM {self.table} WHERE collection = %s ORDER BY doc_id, page, chunk_id",
            (collection,),
        ).fetchall()
        return [Chunk.model_validate(r[0]) for r in rows]

    def vector_search(
        self, collection: str, query: np.ndarray, k: int
    ) -> list[tuple[Chunk, float]]:
        rows = self.conn.execute(
            f"""
            SELECT data, 1 - (embedding <=> %s) AS score
            FROM {self.table} WHERE collection = %s
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (query, collection, query, k),
        ).fetchall()
        return [(Chunk.model_validate(r[0]), float(r[1])) for r in rows]
