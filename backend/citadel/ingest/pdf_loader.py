"""PDF extraction: page-level text and tables, with OCR fallback for unreadable pages.

Design notes:
- PyMuPDF gives exact page numbers and font information (used for heading detection).
- Pages whose text layer is garbled (broken font encodings) or missing (scans) are
  re-read with Tesseract OCR via PyMuPDF.
- Tables are rebuilt cell by cell from word positions. PyMuPDF's own cell text glues
  words together on many university PDFs ("OccupationalSafetyandDisasterManagement"),
  which hurts both BM25 and embeddings.
"""

from __future__ import annotations

import logging
import re
import statistics
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from citadel.ingest.metadata import detect_course_header, looks_like_heading
from citadel.models import Block

log = logging.getLogger(__name__)

GARBLED_CTRL_RATIO = 0.01  # share of control characters above which a text layer is unusable
MIN_TEXT_CHARS = 50  # below this, a page with images is treated as scanned
BOLD_FLAG = 16  # PyMuPDF span flag bit for bold text


@dataclass
class PageReport:
    """What happened to one page during extraction (for `citadel inspect`)."""

    page: int
    ocr: bool
    reason: str
    tables: int
    chars: int


def needs_ocr(page: pymupdf.Page) -> tuple[bool, str]:
    """Decide whether a page's embedded text is unusable and must be OCR'd.

    Returns ``(needs_ocr, reason)`` where reason is ``"ok"``, ``"garbled"`` or ``"scanned"``.
    """
    text = page.get_text()
    stripped = text.strip()
    if len(stripped) < MIN_TEXT_CHARS:
        return (bool(page.get_images()), "scanned" if page.get_images() else "ok")
    ctrl = sum(1 for c in text if ord(c) < 32 and c not in "\n\t\r")
    if ctrl / len(text) > GARBLED_CTRL_RATIO or text.count("�") / len(text) > 0.01:
        return True, "garbled"
    return False, "ok"


def clean_ocr_text(text: str) -> str:
    """Drop OCR noise lines (stray symbols, fragments of rotated table headers).

    A line is kept only if it contains at least one word of three or more letters.
    """
    keep = [ln.strip() for ln in text.splitlines() if re.search(r"[A-Za-z]{3,}", ln)]
    return "\n".join(keep)


def _table_rows(table: pymupdf.table.Table, words: list[tuple]) -> list[str]:
    """Render a table as ``cell | cell | cell`` lines, rebuilding cell text from words.

    Merged cells appear repeatedly in PyMuPDF's grid; consecutive duplicates are collapsed.
    """
    lines: list[str] = []
    for row in table.rows:
        cells: list[str] = []
        for bbox in row.cells:
            if bbox is None:
                continue
            x0, y0, x1, y1 = bbox
            inside = [
                w for w in words if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1
            ]
            inside.sort(key=lambda w: (round(w[1]), w[0]))
            text = " ".join(w[4] for w in inside).strip()
            if text and (not cells or cells[-1] != text):
                cells.append(text)
        if cells:
            lines.append(" | ".join(cells))
    return lines


def _in_any(bbox: tuple[float, float, float, float], regions: list[pymupdf.Rect]) -> bool:
    """True if the centre of ``bbox`` falls inside any of ``regions``."""
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return any(r.contains(pymupdf.Point(cx, cy)) for r in regions)


def _body_font_size(page_dict: dict) -> float:
    """Most common span font size on the page, weighted by character count."""
    sizes: list[float] = []
    for block in page_dict["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                sizes.extend([round(span["size"], 1)] * len(span["text"].strip()))
    return statistics.mode(sizes) if sizes else 10.0


@dataclass
class SectionState:
    """Section tracking carried across pages.

    Once a course syllabus starts (``course`` is set), every block is labelled with the
    course until the next course header: headings inside a syllabus ("Unit-2",
    "Learning Resources", numbered book lists) are too noisy to be useful section names.
    """

    section: str | None = None
    course: str | None = None

    def start_page(self, page_text: str) -> None:
        course = detect_course_header(page_text)
        if course:
            self.course = self.section = course

    def heading(self, text: str) -> None:
        if self.course is None:
            self.section = text


def _digital_page_blocks(
    page: pymupdf.Page, page_no: int, state: SectionState
) -> tuple[list[Block], int]:
    """Extract blocks from a page with a usable text layer. Returns blocks and table count."""
    words = page.get_text("words")
    tables = page.find_tables().tables
    regions = [pymupdf.Rect(t.bbox) for t in tables]
    items: list[tuple[float, float, Block | str]] = []  # (y, x, block or heading)

    for t in tables:
        rows = _table_rows(t, words)
        if rows:
            items.append(
                (t.bbox[1], t.bbox[0], Block(page=page_no, kind="table", text="\n".join(rows)))
            )

    page_dict = page.get_text("dict")
    body = _body_font_size(page_dict)
    for block in page_dict["blocks"]:
        if block.get("type") != 0 or _in_any(block["bbox"], regions):
            continue
        para: list[str] = []
        for line in block["lines"]:
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = " ".join(s["text"].strip() for s in spans)
            size = max(s["size"] for s in spans)
            bold = all(s["flags"] & BOLD_FLAG for s in spans)
            if looks_like_heading(text, size=size, body_size=body, bold=bold):
                if para:
                    items.append((block["bbox"][1], block["bbox"][0], " ".join(para)))
                    para = []
                items.append((line["bbox"][1], line["bbox"][0], f"\x00HEADING\x00{text}"))
            else:
                para.append(text)
        if para:
            items.append((block["bbox"][1], block["bbox"][0], " ".join(para)))

    items.sort(key=lambda it: (round(it[0]), it[1]))
    state.start_page(page.get_text())

    blocks: list[Block] = []
    for _, _, item in items:
        if isinstance(item, Block):
            item.section = state.section
            blocks.append(item)
        elif item.startswith("\x00HEADING\x00"):
            heading = item.removeprefix("\x00HEADING\x00")
            state.heading(heading)
            blocks.append(Block(page=page_no, kind="text", text=heading, section=state.section))
        else:
            blocks.append(Block(page=page_no, kind="text", text=item, section=state.section))
    return blocks, len(tables)


def _ocr_page_blocks(
    page: pymupdf.Page, page_no: int, state: SectionState, dpi: int, language: str
) -> list[Block]:
    """OCR a page and split it into paragraph blocks (blank lines separate paragraphs)."""
    textpage = page.get_textpage_ocr(dpi=dpi, full=True, language=language)
    raw = page.get_text(textpage=textpage)
    state.start_page(raw)
    blocks: list[Block] = []
    for para in re.split(r"\n\s*\n", re.sub(r"[ \t]+\n", "\n", raw)):
        text = clean_ocr_text(para)
        if not text:
            continue
        first = text.splitlines()[0]
        if looks_like_heading(first, size=0, body_size=0, bold=False):
            state.heading(first)
        blocks.append(Block(page=page_no, kind="text", text=text, section=state.section, ocr=True))
    return blocks


def load_pdf(
    path: Path, dpi: int = 300, language: str = "eng"
) -> tuple[list[Block], list[PageReport], pymupdf.Document]:
    """Extract all pages of a PDF into blocks.

    Returns the blocks, a per-page report, and the open document (for metadata).
    """
    doc = pymupdf.open(path)
    blocks: list[Block] = []
    reports: list[PageReport] = []
    state = SectionState()
    for index in range(doc.page_count):
        page = doc[index]
        page_no = index + 1
        ocr, reason = needs_ocr(page)
        if ocr:
            try:
                page_blocks = _ocr_page_blocks(page, page_no, state, dpi, language)
                tables = 0
            except RuntimeError as exc:  # Tesseract not installed / language missing
                log.warning("OCR failed on %s p.%d (%s); skipping page", path.name, page_no, exc)
                page_blocks, tables = [], 0
        else:
            page_blocks, tables = _digital_page_blocks(page, page_no, state)
        blocks.extend(page_blocks)
        reports.append(
            PageReport(
                page=page_no,
                ocr=ocr,
                reason=reason,
                tables=tables,
                chars=sum(len(b.text) for b in page_blocks),
            )
        )
    return blocks, reports, doc
