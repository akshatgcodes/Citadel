"""Chunking behaviour: size limits, overlap, page/section boundaries, tables, fragments."""

from __future__ import annotations

import pytest

from citadel.ingest.chunker import (
    chunk_document,
    pack_table,
    pack_units,
    split_units,
    whitespace_counter,
)
from citadel.models import Block, Document

count = whitespace_counter


def make_doc() -> Document:
    return Document(
        doc_id="regs", title="Academic Regulations", source_path="regs.pdf", doc_type="pdf"
    )


def sentences(n: int, words: int = 10, tag: str = "s") -> str:
    """n distinct sentences of ``words`` words each, e.g. 'S0w0 s0w1 ... s0w9.'"""
    return " ".join(
        " ".join(f"{tag}{i}w{j}" for j in range(words)).capitalize() + "." for i in range(n)
    )


def test_split_units_on_sentences_and_lines() -> None:
    units = split_units("First rule applies. Second rule too!\n- bullet one\n- bullet two")
    assert units == ["First rule applies.", "Second rule too!", "- bullet one", "- bullet two"]


def test_pack_units_respects_size() -> None:
    units = split_units(sentences(20))  # 20 sentences x 10 words
    windows = pack_units(units, size=35, overlap=10, count=count)
    assert all(count(w) <= 35 for w in windows)
    assert len(windows) > 1


def test_pack_units_overlap_repeats_trailing_sentence() -> None:
    units = split_units(sentences(6))
    windows = pack_units(units, size=30, overlap=10, count=count)
    # each window ends with a sentence that the next window starts with
    for left, right in zip(windows, windows[1:], strict=False):
        last_sentence = split_units(left)[-1]
        assert right.startswith(last_sentence)


def test_pack_units_no_overlap() -> None:
    units = split_units(sentences(6))
    windows = pack_units(units, size=30, overlap=0, count=count)
    joined = " ".join(windows)
    assert joined == " ".join(units)  # nothing duplicated, nothing lost


def test_oversize_sentence_is_split_into_windows() -> None:
    long_sentence = " ".join(f"w{i}" for i in range(100))
    windows = pack_units([long_sentence], size=30, overlap=5, count=count)
    assert all(count(w) <= 30 for w in windows)
    assert windows[0].split()[0] == "w0" and windows[-1].split()[-1] == "w99"


def test_small_table_kept_whole() -> None:
    table = "Grade | Points\nO | 10\nA+ | 9"
    assert pack_table(table, size=50, count=count) == [table]


def test_large_table_split_by_rows_repeats_header() -> None:
    header = "Course Code | Title | Credits"
    rows = [f"21CS{i:03d} | Course number {i} | 3" for i in range(40)]
    pieces = pack_table("\n".join([header, *rows]), size=40, count=count)
    assert len(pieces) > 1
    assert all(p.splitlines()[0] == header for p in pieces)
    body_rows = [r for p in pieces for r in p.splitlines()[1:]]
    assert body_rows == rows  # every row exactly once, in order


def test_chunks_never_cross_pages_or_sections() -> None:
    blocks = [
        Block(page=1, kind="text", text=sentences(8, tag="a"), section="Attendance"),
        Block(page=1, kind="text", text=sentences(8, tag="b"), section="Examinations"),
        Block(page=2, kind="text", text=sentences(8, tag="c"), section="Examinations"),
    ]
    chunks = chunk_document(make_doc(), blocks, chunk_size=50, overlap=10)
    for c in chunks:
        tags = {w[0].lower() for w in c.text.split()}
        assert len(tags) == 1  # one source block per chunk
        expected = {"a": (1, "Attendance"), "b": (1, "Examinations"), "c": (2, "Examinations")}
        assert (c.page, c.section) == expected[tags.pop()]


def test_chunk_metadata_and_ids() -> None:
    doc = make_doc().model_copy(update={"date": "2024-06-01", "regulation": "R2021"})
    blocks = [Block(page=3, kind="text", text=sentences(10), section="Credits")]
    chunks = chunk_document(doc, blocks, chunk_size=40, overlap=5)
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert all(c.page == 3 and c.date == "2024-06-01" and c.regulation == "R2021" for c in chunks)
    assert chunks[0].citation_label() == "Academic Regulations, p. 3"
    assert chunks[0].embedding_text().startswith("Academic Regulations > Credits\n")


def test_tables_do_not_merge_with_neighbouring_text() -> None:
    blocks = [
        Block(page=1, kind="text", text=sentences(4), section="Grading"),
        Block(
            page=1,
            kind="table",
            text="Grade | Points\n" + "\n".join(f"G{i} | {i}" for i in range(30)),
            section="Grading",
        ),
        Block(page=1, kind="text", text=sentences(4, tag="t"), section="Grading"),
    ]
    chunks = chunk_document(make_doc(), blocks, chunk_size=200, overlap=10)
    assert [c.kind for c in chunks] == ["text", "table", "text"]


def test_tiny_fragment_merged_into_previous_chunk_on_same_page() -> None:
    blocks = [
        Block(page=1, kind="text", text=sentences(5), section="Fees"),
        Block(page=1, kind="table", text="PSO-1 PSO-2", section="Fees"),  # scrap of a table header
    ]
    chunks = chunk_document(make_doc(), blocks, chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].text.endswith("PSO-1 PSO-2")


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        chunk_document(make_doc(), [], chunk_size=50, overlap=50)
