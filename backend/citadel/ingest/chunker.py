"""Structure-aware chunking.

Rules (each one is a deliberate trade-off):
- A chunk never crosses a page boundary, so every chunk has exactly one page to cite.
  The cost is the occasional sentence split at a page break.
- A chunk never crosses a section boundary, so it is about one topic and its section
  label is accurate.
- Text is packed sentence by sentence up to ``chunk_size`` tokens, with roughly
  ``overlap`` tokens of trailing sentences repeated at the start of the next chunk, so
  a fact that straddles a boundary is fully present in at least one chunk.
- Tables are kept whole when they fit. Larger tables are split by rows, and every
  piece repeats the table's first row, so each piece still says what its columns mean.
- Sizes are measured in tokens of the embedding model's tokenizer (not characters),
  because the embedding model truncates by tokens.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from functools import lru_cache
from itertools import groupby

from citadel.models import Block, Chunk, Document

TokenCounter = Callable[[str], int]

SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9(\"'])|\n+")


def whitespace_counter(text: str) -> int:
    """Cheap token approximation (word count). Used in tests."""
    return len(text.split())


@lru_cache(maxsize=4)
def tokenizer_counter(model_name: str) -> TokenCounter:
    """Token counter backed by the embedding model's own tokenizer."""
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.model_max_length = 10**9  # we only count tokens here; silence length warnings

    def count(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    return count


def split_units(text: str) -> list[str]:
    """Split text into sentence-like units (sentences, list items, lines)."""
    return [u.strip() for u in SENTENCE_SPLIT.split(text) if u and u.strip()]


def _split_long_unit(unit: str, size: int, overlap: int, count: TokenCounter) -> list[str]:
    """Split a single oversize unit into word windows of at most ``size`` tokens.

    Per-word token counts are summed (a close approximation of tokenising the joined
    string) so this stays linear in the number of words.
    """
    words = unit.split()
    costs = [max(count(w), 1) for w in words]
    pieces: list[str] = []
    start = 0
    while start < len(words):
        end, used = start, 0
        while end < len(words) and (end == start or used + costs[end] <= size):
            used += costs[end]
            end += 1
        pieces.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        back, carried = end, 0
        while back > start + 1 and carried + costs[back - 1] <= overlap:
            back -= 1
            carried += costs[back]
        start = back
    return pieces


def pack_units(units: list[str], size: int, overlap: int, count: TokenCounter) -> list[str]:
    """Greedily pack units into windows of at most ``size`` tokens with unit-level overlap."""
    expanded: list[str] = []
    for unit in units:
        if count(unit) > size:
            expanded.extend(_split_long_unit(unit, size, overlap, count))
        else:
            expanded.append(unit)

    windows: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for unit in expanded:
        n = count(unit)
        if current and current_tokens + n > size:
            windows.append(" ".join(current))
            # carry trailing units forward as overlap
            carry: list[str] = []
            carry_tokens = 0
            for prev in reversed(current):
                t = count(prev)
                if carry_tokens + t > overlap or carry_tokens + t + n > size:
                    break
                carry.insert(0, prev)
                carry_tokens += t
            current, current_tokens = carry, carry_tokens
        current.append(unit)
        current_tokens += n
    if current:
        windows.append(" ".join(current))
    return windows


def pack_table(text: str, size: int, count: TokenCounter) -> list[str]:
    """Keep a table whole if it fits; otherwise split by rows, repeating the first row."""
    if count(text) <= size:
        return [text]
    rows = [r for r in text.splitlines() if r.strip()]
    header, body = rows[0], rows[1:]
    header_tokens = count(header)
    if header_tokens > size // 2:  # header too big to repeat usefully
        header, body, header_tokens = "", rows, 0
    pieces: list[str] = []
    current: list[str] = []
    current_tokens = header_tokens
    for row in body:
        n = count(row)
        if n + header_tokens > size:  # a single giant row: fall back to word windows
            if current:
                pieces.append("\n".join(([header] if header else []) + current))
                current, current_tokens = [], header_tokens
            pieces.extend(_split_long_unit(row, size, 0, count))
            continue
        if current and current_tokens + n > size:
            pieces.append("\n".join(([header] if header else []) + current))
            current, current_tokens = [], header_tokens
        current.append(row)
        current_tokens += n
    if current:
        pieces.append("\n".join(([header] if header else []) + current))
    return pieces


def chunk_document(
    doc: Document,
    blocks: Iterable[Block],
    *,
    chunk_size: int,
    overlap: int,
    count: TokenCounter = whitespace_counter,
) -> list[Chunk]:
    """Turn a document's blocks into citable chunks.

    Consecutive text blocks on the same page and section are merged before packing;
    each table becomes its own chunk(s).
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[Chunk] = []

    def emit(text: str, block: Block) -> None:
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}:p{block.page}:{len(chunks)}",
                doc_id=doc.doc_id,
                doc_title=doc.title,
                page=block.page,
                section=block.section,
                date=doc.date,
                regulation=doc.regulation,
                doc_type=doc.doc_type,
                kind=block.kind,
                ocr=block.ocr,
                text=text,
                token_count=count(text),
            )
        )

    def group_key(b: Block) -> tuple:
        # tables never merge with neighbours; text merges within (page, section)
        return (b.page, b.section, b.kind, id(b) if b.kind == "table" else 0)

    for _, group in groupby(blocks, key=group_key):
        members = list(group)
        first = members[0]
        if first.kind == "table":
            for piece in pack_table(first.text, chunk_size, count):
                emit(piece, first)
            continue
        units = [u for b in members for u in split_units(b.text)]
        for window in pack_units(units, chunk_size, overlap, count):
            emit(window, first)
    return merge_small_chunks(
        chunks, min_tokens=min(MIN_CHUNK_TOKENS, chunk_size // 4), count=count
    )


MIN_CHUNK_TOKENS = 25


def merge_small_chunks(chunks: list[Chunk], *, min_tokens: int, count: TokenCounter) -> list[Chunk]:
    """Fold fragments (a lone heading, scraps of rotated table headers) into a neighbour.

    A tiny chunk is appended to the previous chunk on the same page, or prepended to the
    next one if it starts a page. Fragments alone embed poorly and crowd out real results.
    Chunk ids are reassigned afterwards so they stay sequential.
    """
    merged: list[Chunk] = []
    pending: Chunk | None = None  # small chunk waiting to be prepended to the next one
    for chunk in chunks:
        if pending is not None:
            if pending.page == chunk.page and pending.doc_id == chunk.doc_id:
                chunk = chunk.model_copy(update={"text": f"{pending.text}\n{chunk.text}"})
            else:
                merged.append(pending)
            pending = None
        if chunk.token_count < min_tokens:
            prev = merged[-1] if merged else None
            if prev is not None and prev.page == chunk.page and prev.doc_id == chunk.doc_id:
                merged[-1] = prev.model_copy(update={"text": f"{prev.text}\n{chunk.text}"})
            else:
                pending = chunk
            continue
        merged.append(chunk)
    if pending is not None:
        merged.append(pending)
    for i, chunk in enumerate(merged):
        chunk.chunk_id = f"{chunk.doc_id}:p{chunk.page}:{i}"
        chunk.token_count = count(chunk.text)
    return merged
