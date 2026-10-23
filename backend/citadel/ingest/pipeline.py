"""Ingestion pipeline: data/raw → blocks → chunks → embeddings → store.

Each run re-ingests the whole collection for the current config. At this corpus size that
takes a minute or two, and it guarantees the store matches `data/raw/` exactly (no stale
chunks from deleted or edited files).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from citadel.config import Settings
from citadel.ingest.chunker import chunk_document, tokenizer_counter
from citadel.ingest.html_loader import html_title, load_html
from citadel.ingest.metadata import (
    clean_title,
    detect_date,
    detect_regulation,
    doc_id_for,
    load_manifest,
)
from citadel.ingest.pdf_loader import PageReport, load_pdf
from citadel.models import Block, Chunk, Document
from citadel.store.base import ChunkStore

log = logging.getLogger(__name__)

SUPPORTED = {".pdf": "pdf", ".html": "html", ".htm": "html"}
JUNK_PDF_TITLES = ("microsoft word", "untitled", ".docx", ".doc", ".pdf")


@dataclass
class LoadedDocument:
    """A parsed source file before chunking."""

    document: Document
    blocks: list[Block]
    pages: list[PageReport] = field(default_factory=list)


def discover(raw_dir: Path) -> list[Path]:
    """Supported files in ``raw_dir``, sorted by name."""
    return sorted(p for p in raw_dir.iterdir() if p.suffix.lower() in SUPPORTED)


def load_document(path: Path, settings: Settings, manifest: dict[str, dict]) -> LoadedDocument:
    """Parse one file and work out its document-level metadata."""
    overrides = manifest.get(path.name, {})
    doc_type = SUPPORTED[path.suffix.lower()]
    pages: list[PageReport] = []

    if doc_type == "pdf":
        blocks, pages, pdf = load_pdf(path, dpi=settings.ocr_dpi, language=settings.ocr_language)
        meta_title = (pdf.metadata or {}).get("title") or ""
        if meta_title and not any(j in meta_title.lower() for j in JUNK_PDF_TITLES):
            found_title = meta_title
        else:
            found_title = clean_title(path.stem)
        num_pages = pdf.page_count
        pdf.close()
    else:
        blocks, html = load_html(path)
        found_title = clean_title(html_title(html) or path.stem)
        num_pages = 1

    first_text = " ".join(b.text for b in blocks if b.page == 1)[:3000]
    document = Document(
        doc_id=doc_id_for(path),
        title=overrides.get("title") or found_title,
        source_path=path.name,
        doc_type=doc_type,  # type: ignore[arg-type]
        date=str(overrides["date"])
        if overrides.get("date")
        else detect_date(path.stem, first_text),
        regulation=overrides.get("regulation") or detect_regulation(path.stem, first_text),
        num_pages=num_pages,
    )
    return LoadedDocument(document=document, blocks=blocks, pages=pages)


def write_processed(out_dir: Path, docs: list[LoadedDocument], chunks: list[Chunk]) -> None:
    """Save documents and chunks as JSON/JSONL for debugging and for the eval harness."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "documents.json").write_text(
        json.dumps([d.document.model_dump() for d in docs], indent=2, ensure_ascii=False)
    )
    with (out_dir / "chunks.jsonl").open("w") as fh:
        for c in chunks:
            fh.write(json.dumps(c.model_dump(), ensure_ascii=False) + "\n")


def ingest(
    settings: Settings, store: ChunkStore, embedder: object, show_progress: bool = True
) -> tuple[list[LoadedDocument], list[Chunk]]:
    """Run the full pipeline for the current settings and return what was stored."""
    manifest = load_manifest(settings.manifest_path)
    count = tokenizer_counter(settings.embed_model)

    loaded: list[LoadedDocument] = []
    chunks: list[Chunk] = []
    for path in discover(settings.raw_dir):
        log.info("loading %s", path.name)
        doc = load_document(path, settings, manifest)
        loaded.append(doc)
        chunks.extend(
            chunk_document(
                doc.document,
                doc.blocks,
                chunk_size=settings.chunk_size,
                overlap=settings.chunk_overlap,
                count=count,
            )
        )

    write_processed(settings.processed_dir / settings.collection, loaded, chunks)
    vectors = embedder.embed_passages(  # type: ignore[attr-defined]
        [c.embedding_text() for c in chunks], show_progress=show_progress
    )
    store.delete_collection(settings.collection)
    if chunks:
        store.upsert(settings.collection, chunks, vectors)
    return loaded, chunks
