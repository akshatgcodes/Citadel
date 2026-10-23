"""Command-line entry point: ``citadel inspect | ingest | query``.

Flags override the matching env settings for that run, e.g.
``citadel ingest --chunk-size 256 --overlap 32``.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import textwrap
import warnings

from citadel.config import Settings, get_settings
from citadel.store.base import ChunkStore

# Model libraries are chatty (progress bars, deprecation notices); keep CLI output readable.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
warnings.filterwarnings("ignore", category=FutureWarning)


def _settings(args: argparse.Namespace) -> Settings:
    overrides = {
        key: value
        for key, value in {
            "chunk_size": getattr(args, "chunk_size", None),
            "chunk_overlap": getattr(args, "overlap", None),
            "embed_model": getattr(args, "embed_model", None),
        }.items()
        if value is not None
    }
    return get_settings().model_copy(update=overrides)


def _store(settings: Settings, dim: int) -> ChunkStore:
    if settings.vector_store == "local":
        from citadel.store.base import LocalStore

        return LocalStore(settings.processed_dir)
    from citadel.store.pgvector_store import PgVectorStore

    return PgVectorStore(settings.database_url, dim)


def cmd_inspect(args: argparse.Namespace) -> None:
    """Show what extraction finds in each file, without embedding anything."""
    from citadel.ingest.metadata import load_manifest
    from citadel.ingest.pipeline import discover, load_document

    settings = _settings(args)
    manifest = load_manifest(settings.manifest_path)
    for path in discover(settings.raw_dir):
        doc = load_document(path, settings, manifest)
        d = doc.document
        print(f"\n== {path.name}")
        print(f"   title: {d.title} | type: {d.doc_type} | pages: {d.num_pages}")
        print(f"   date: {d.date} | regulation: {d.regulation}")
        ocr = [p.page for p in doc.pages if p.ocr]
        tables = sum(1 for b in doc.blocks if b.kind == "table")
        sections = list(dict.fromkeys(b.section for b in doc.blocks if b.section))
        print(f"   blocks: {len(doc.blocks)} | tables: {tables} | OCR pages: {ocr or 'none'}")
        print(
            f"   sections ({len(sections)}): {sections[:12]}{' ...' if len(sections) > 12 else ''}"
        )


def cmd_ingest(args: argparse.Namespace) -> None:
    """Extract, chunk, embed and store every file in data/raw/."""
    from citadel.ingest.pipeline import ingest
    from citadel.store.embedder import get_embedder

    settings = _settings(args)
    embedder = get_embedder(
        settings.embed_model, settings.embed_query_prefix, settings.embed_batch_size
    )
    store = _store(settings, embedder.dim)
    docs, chunks = ingest(settings, store, embedder)
    print(f"\nIngested {len(docs)} documents → {len(chunks)} chunks")
    print(f"collection: {settings.collection}")
    for d in docs:
        n = sum(1 for c in chunks if c.doc_id == d.document.doc_id)
        print(f"  {n:4d} chunks  {d.document.title}")


def cmd_query(args: argparse.Namespace) -> None:
    """Run retrieval for a question and print the ranked chunks."""
    from citadel.retrieval.reranker import get_reranker
    from citadel.retrieval.retriever import Retriever
    from citadel.store.embedder import get_embedder

    settings = _settings(args)
    embedder = get_embedder(
        settings.embed_model, settings.embed_query_prefix, settings.embed_batch_size
    )
    retriever = Retriever(
        _store(settings, embedder.dim),
        settings.collection,
        embedder,
        reranker_factory=lambda: get_reranker(settings.rerank_model),
        rrf_k=settings.rrf_k,
    )
    result = retriever.retrieve(
        args.question,
        k=args.k or settings.top_k,
        mode=args.mode or settings.retrieval_mode,
        rerank=args.rerank if args.rerank is not None else settings.rerank,
        candidates=settings.rerank_candidates,
    )
    timing = ", ".join(f"{k}={v:.0f}" for k, v in result.timings_ms.items())
    print(f"\nQ: {args.question}\n({timing})")
    for i, r in enumerate(result.chunks, start=1):
        parts = [f"score={r.score:.4f}"]
        if r.vector_rank:
            parts.append(f"vec#{r.vector_rank}={r.vector_score:.3f}")
        if r.bm25_rank:
            parts.append(f"bm25#{r.bm25_rank}={r.bm25_score:.2f}")
        if r.rerank_score is not None:
            parts.append(f"rerank={r.rerank_score:.2f}")
        c = r.chunk
        section = f"  §{c.section}" if c.section and c.doc_type == "pdf" else ""
        print(f"\n[{i}] {c.citation_label()}{section}  ({c.kind}{', OCR' if c.ocr else ''})")
        print("    " + "  ".join(parts))
        print(textwrap.indent(textwrap.shorten(c.text, 400, placeholder=" …"), "    "))


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and dispatch to a subcommand."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("huggingface_hub", "torch.distributed.elastic.multiprocessing.redirects"):
        logging.getLogger(noisy).setLevel(logging.ERROR)
    parser = argparse.ArgumentParser(prog="citadel", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def chunk_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--chunk-size", type=int, help="tokens per chunk")
        p.add_argument("--overlap", type=int, help="overlap tokens between chunks")
        p.add_argument("--embed-model", help="sentence-transformers model name")

    p = sub.add_parser("inspect", help="show extraction results per file")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("ingest", help="extract, chunk, embed and store documents")
    chunk_flags(p)
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("query", help="retrieve chunks for a question")
    p.add_argument("question")
    p.add_argument("-k", type=int)
    p.add_argument("--mode", choices=["vector", "bm25", "hybrid"])
    p.add_argument("--rerank", action=argparse.BooleanOptionalAction, default=None)
    chunk_flags(p)
    p.set_defaults(func=cmd_query)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
