"""Core data types shared by ingestion, storage and retrieval."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BlockKind = Literal["text", "table"]


class Document(BaseModel):
    """One source file in `data/raw/`."""

    doc_id: str
    title: str
    source_path: str
    doc_type: Literal["pdf", "html"]
    date: str | None = None  # ISO date or academic year as written, e.g. "2026-27"
    regulation: str | None = None  # e.g. "R2021"
    num_pages: int = 1


class Block(BaseModel):
    """A contiguous piece of extracted content on one page."""

    page: int  # 1-based PDF page index; HTML documents are a single page
    kind: BlockKind
    text: str
    section: str | None = None  # nearest heading above this block
    ocr: bool = False


class Chunk(BaseModel):
    """A retrievable unit: text plus the metadata needed to cite it."""

    chunk_id: str
    doc_id: str
    doc_title: str
    page: int
    section: str | None = None
    date: str | None = None
    regulation: str | None = None
    doc_type: Literal["pdf", "html"] = "pdf"
    kind: BlockKind = "text"
    ocr: bool = False
    text: str
    token_count: int = 0

    def citation_label(self) -> str:
        """Source label used in citations: ``Exam Rules, p. 4`` or ``Code of Conduct, §Appeals``."""
        if self.doc_type == "html":
            return f"{self.doc_title}, §{self.section}" if self.section else self.doc_title
        return f"{self.doc_title}, p. {self.page}"

    def embedding_text(self) -> str:
        """Text that gets embedded and BM25-indexed.

        A short header (title and section) is prepended so a chunk that says
        "the minimum is 75%" can still be found by a query mentioning "attendance".
        """
        header = self.doc_title + (f" > {self.section}" if self.section else "")
        return f"{header}\n{self.text}"


class RetrievedChunk(BaseModel):
    """A chunk returned by the retriever, with the scores from each stage."""

    chunk: Chunk
    score: float  # final score used for ordering
    vector_score: float | None = None
    vector_rank: int | None = None
    bm25_score: float | None = None
    bm25_rank: int | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


class RetrievalResult(BaseModel):
    """Retriever output plus per-stage timings in milliseconds."""

    query: str
    chunks: list[RetrievedChunk]
    timings_ms: dict[str, float] = Field(default_factory=dict)
