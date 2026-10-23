"""HTML extraction: main content only, split into sections by heading.

trafilatura removes navigation, menus and footers (a saved university page is mostly
site chrome) and returns Markdown, from which headings become section names and
Markdown tables become table blocks.
"""

from __future__ import annotations

import re
from pathlib import Path

import trafilatura
from bs4 import BeautifulSoup

from citadel.models import Block

HEADING = re.compile(r"^#{1,6}\s+(.*)$")
TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}")


def strip_markdown(text: str) -> str:
    """Remove emphasis/underline markup and escapes that trafilatura leaves in place."""
    text = re.sub(r"</?u>", "", text)
    text = re.sub(r"\*\*|__", "", text)
    text = re.sub(r"(?<!\w)[*_](\S[^*_]*?)[*_](?!\w)", r"\1", text)
    return text.replace("\\*", "*").replace("\\_", "_").strip()


def html_title(html: str) -> str | None:
    """Return the page's <title> text, if any."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.title.get_text(strip=True) if soup.title else None


def load_html(path: Path) -> tuple[list[Block], str]:
    """Extract main-content blocks from an HTML file.

    Returns the blocks (all on page 1) and the full raw HTML (for metadata detection).
    """
    html = path.read_text(errors="ignore")
    markdown = (
        trafilatura.extract(
            html,
            output_format="markdown",
            include_tables=True,
            include_formatting=True,
            include_links=False,
            favor_recall=True,
        )
        or ""
    )

    blocks: list[Block] = []
    section: str | None = None
    para: list[str] = []
    table: list[str] = []

    def flush_para() -> None:
        if para:
            blocks.append(Block(page=1, kind="text", text="\n".join(para), section=section))
            para.clear()

    def flush_table() -> None:
        if table:
            rows = [
                " | ".join(c.strip() for c in ln.strip().strip("|").split("|") if c.strip())
                for ln in table
                if not TABLE_RULE.match(ln)
            ]
            blocks.append(
                Block(page=1, kind="table", text="\n".join(r for r in rows if r), section=section)
            )
            table.clear()

    for line in markdown.splitlines():
        if TABLE_LINE.match(line):
            flush_para()
            table.append(strip_markdown(line))
            continue
        flush_table()
        if m := HEADING.match(line):
            flush_para()
            section = strip_markdown(m.group(1)).rstrip(":")
            continue
        if not line.strip():
            flush_para()
            continue
        para.append(strip_markdown(re.sub(r"^\s*[-*]\s+", "- ", line)))
    flush_para()
    flush_table()
    return [b for b in blocks if b.text.strip()], html
