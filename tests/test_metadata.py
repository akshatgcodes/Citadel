"""Metadata heuristics: headings, course headers, dates, regulations, titles."""

from __future__ import annotations

import pytest

from citadel.ingest.metadata import (
    clean_title,
    detect_course_header,
    detect_date,
    detect_regulation,
    looks_like_heading,
)
from citadel.ingest.pdf_loader import clean_ocr_text


@pytest.mark.parametrize(
    "text",
    [
        "3.2 Attendance Requirements",
        "Unit-4: Environment and Disaster Management",
        "CHAPTER III EXAMINATIONS",
    ],
)
def test_headings_detected(text: str) -> None:
    assert looks_like_heading(text, size=10, body_size=10, bold=False)


@pytest.mark.parametrize(
    "text",
    [
        "Students must attend at least 75% of classes in every course.",
        "7. Python Datascience Handbook, Oreilly, Jake VanderPlas, 2017.",
        "1. Dr. E. Poovammal, SRMIST",
        "9. https://www.tutorialspoint.com/python/index.htm",
        "(40% Weightage)",
    ],
)
def test_non_headings_rejected(text: str) -> None:
    assert not looks_like_heading(text, size=10, body_size=10, bold=True)


def test_larger_font_line_is_heading() -> None:
    assert looks_like_heading("Fee Refund Policy", size=14, body_size=10, bold=False)
    assert not looks_like_heading("Fee Refund Policy", size=10, body_size=10, bold=False)


def test_course_header() -> None:
    text = "Course \nCode \n21CSS201T \nCourse Name \nCOMPUTER ORGANIZATION AND ARCHITECTURE \nCourse \nCategory S"
    assert detect_course_header(text) == "21CSS201T Computer Organization And Architecture"


@pytest.mark.parametrize(
    ("texts", "expected"),
    [
        (("21MEO105T - Syllabus  2026-27",), "2026-27"),
        (("circular", "Dated 05.07.2025: revised schedule"), "2025-07-05"),
        (("notice", "Issued on 3rd March, 2026"), "2026-03-03"),
        (("syllabus", "Pages 2019-2024 of the archive"), None),  # not an academic year
    ],
)
def test_detect_date(texts: tuple[str, ...], expected: str | None) -> None:
    assert detect_date(*texts) == expected


def test_detect_regulation() -> None:
    assert detect_regulation("csc-r2021-curriculum") == "R2021"
    assert detect_regulation("x", "Academic Regulations 2024 (applicable from...)") == "R2024"
    assert detect_regulation("syllabus") is None


def test_clean_title() -> None:
    assert (
        clean_title("Code of Conduct for Students | Policies - SRMIST")
        == "Code of Conduct for Students"
    )
    assert clean_title("exam-rules") == "Exam Rules"


def test_clean_ocr_text_drops_noise_lines() -> None:
    noisy = "S/S5/22/8/5/S4e/8|\nUnit-1: Finite Automata\n@\\/e4\nregular expressions"
    assert clean_ocr_text(noisy) == "Unit-1: Finite Automata\nregular expressions"
