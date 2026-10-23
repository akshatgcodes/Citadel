"""Metadata detection: headings, titles, dates, regulation versions, manifest overrides.

Priority for document-level fields is: `data/manifest.yaml` > values found in the file
(filename, first page, HTML <title>) > nothing. A missing date is better than a wrong one,
so PDF creation dates are never used (a 2026-27 syllabus here was "created" in 2022).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

NUMBERED_HEADING = re.compile(
    r"^(\d{1,2}(\.\d{1,2})*\.?|[IVX]{1,5}\.|[A-Z]\.|Unit\s*[-–]?\s*\d+\s*:?|Chapter\s+\d+|"
    r"Section\s+\d+|Rule\s+\d+|Clause\s+\d+)\s+\S"
)
COURSE_HEADER = re.compile(
    r"Course\s*Code\s*:?\s*(?P<code>\d{2}[A-Z]{3}\d{3}[A-Z])\s*Course\s*Name\s*:?\s*"
    r"(?P<name>.+?)\s*Course\s*Category",
    re.IGNORECASE | re.DOTALL,
)
REGULATION = re.compile(r"\b(?:R\s?|Regulations?\s*[-–]?\s*)(20\d{2})\b", re.IGNORECASE)
ACADEMIC_YEAR = re.compile(r"\b(20\d{2})\s*[-–/]\s*(\d{2}|20\d{2})\b")
FULL_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b")
MONTH_DATE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+"
    r"(20\d{2})\b",
    re.IGNORECASE,
)
MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}


def looks_like_heading(text: str, *, size: float, body_size: float, bold: bool) -> bool:
    """Heuristic heading detector for a single line of PDF text.

    A heading is short, contains letters, does not read like a sentence, and is either
    visually prominent (larger or bold font) or numbered like ``3.2 Attendance``.
    ``size``/``body_size`` of 0 means font info is unavailable (OCR); only the numbering
    and ALL-CAPS rules apply then.
    """
    text = text.strip()
    if not (3 <= len(text) <= 90) or not re.search(r"[A-Za-z]{3,}", text):
        return False
    if not text[0].isalnum() or re.search(r"https?://|www\.|@|\bDr\.|\bProf\.|ISBN", text):
        return False  # bracketed notes, links, emails, people and book references
    if re.search(r",\s*(19|20)\d{2}\b", text):
        return False  # citation-style "Title, Publisher, 2017"
    if text.endswith((".", ",", ";")) and not NUMBERED_HEADING.match(text):
        return False
    if len(text.split()) > 12:
        return False
    if NUMBERED_HEADING.match(text) and len(text.split()) <= 10:
        return True
    if body_size and size >= body_size * 1.15:
        return True
    if bold and len(text.split()) <= 8:
        return True
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 8 and all(c.isupper() for c in letters) and len(text.split()) <= 8


def detect_course_header(page_text: str) -> str | None:
    """Return ``"<code> <name>"`` if the page starts a course syllabus, else None."""
    match = COURSE_HEADER.search(" ".join(page_text.split()))
    if not match:
        return None
    name = match["name"].strip(" :|")
    if name.isupper():
        name = name.title()
    return f"{match['code'].upper()} {name}"


def detect_regulation(*texts: str) -> str | None:
    """Find a regulation version such as ``R2021`` in the filename or first page."""
    for text in texts:
        match = REGULATION.search(text)
        if match:
            return f"R{match.group(1)}"
    return None


def detect_date(*texts: str) -> str | None:
    """Find the most specific date in the given texts (filename first, then first page).

    Returns ISO ``YYYY-MM-DD`` for full dates, or the academic year as written (``2026-27``).
    """
    for text in texts:
        if m := MONTH_DATE.search(text):
            return f"{m.group(3)}-{MONTHS[m.group(2)[:3].lower()]:02d}-{int(m.group(1)):02d}"
        if m := FULL_DATE.search(text):
            day, month = int(m.group(1)), int(m.group(2))
            if 1 <= day <= 31 and 1 <= month <= 12:  # Indian documents use DD.MM.YYYY
                return f"{m.group(3)}-{month:02d}-{day:02d}"
        if m := ACADEMIC_YEAR.search(text):
            end = m.group(2)[-2:]
            if int(end) == (int(m.group(1)) + 1) % 100:
                return f"{m.group(1)}-{end}"
    return None


def clean_title(raw: str) -> str:
    """Turn an HTML <title> or filename into a readable document title."""
    title = re.split(r"\s+[|–]\s+|\s+-\s+(?=[A-Z][\w ]*$)", raw.strip())[0]
    title = re.sub(r"[_]+", " ", title)
    title = re.sub(r"\s{2,}", " ", title).strip()
    if title == title.lower():
        title = title.replace("-", " ").title()
    return title


def doc_id_for(path: Path) -> str:
    """Stable, filesystem-safe id: slugified filename plus a short content-independent hash."""
    slug = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")[:48]
    digest = hashlib.sha1(path.name.encode()).hexdigest()[:6]
    return f"{slug}-{digest}"


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    """Load per-file overrides keyed by filename. Missing file means no overrides."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return {str(k): (v or {}) for k, v in data.items()}
