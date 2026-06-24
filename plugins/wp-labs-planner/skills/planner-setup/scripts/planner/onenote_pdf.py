"""Parse a OneNote PDF export into per-page records (pure over extracted text)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

_FOOTER = re.compile(r"^(.+?)\s+Page\s+\d+\s*$")
_DATE = re.compile(
    r"^[A-Z][a-z]+day,\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s*[AP]M\s*$"
)
_DATE_FMT = "%A, %B %d, %Y %I:%M %p"


@dataclass
class OneNotePage:
    """A OneNote page extracted from PDF.

    Attributes:
        section: The section name (extracted from page footer).
        title: The page title (typically the first line).
        date: The page date, or None if not found.
        body: The page body text.
    """

    section: str
    title: str
    date: date | None
    body: str


def parse_date(line: str) -> date | None:
    """Parse a OneNote page-date line ('Tuesday, May 26, 2026 4:25 PM') to a date.

    Args:
        line: The line to parse.

    Returns:
        The parsed date, or None if the line does not match the date pattern.
    """
    s = line.strip()
    if not _DATE.match(s):
        return None
    try:
        return datetime.strptime(s, _DATE_FMT).date()
    except ValueError:
        return None


def read_pdf_pages(path: str) -> list[str]:
    """Return the extracted text of each PDF page (thin pypdf wrapper).

    Args:
        path: The path to the PDF file.

    Returns:
        A list of extracted page texts.
    """
    from pypdf import PdfReader

    reader = PdfReader(path)
    return [(page.extract_text() or "") for page in reader.pages]


def _flatten(page_texts: list[str]) -> list[tuple[str, str]]:
    """Return (line, section) for each non-blank, non-footer line; section carries fwd.

    Args:
        page_texts: List of extracted PDF page texts.

    Returns:
        List of (line, section) tuples.
    """
    out: list[tuple[str, str]] = []
    section = ""
    for text in page_texts:
        lines = [ln.strip() for ln in text.splitlines()]
        for ln in lines:  # section comes from any footer on the page
            fm = _FOOTER.match(ln)
            if fm:
                section = fm.group(1).strip()
        for ln in lines:
            if ln and not _FOOTER.match(ln):
                out.append((ln, section))
    return out


def parse_pages(page_texts: list[str]) -> list[OneNotePage]:
    """Segment extracted PDF text into OneNote pages via date lines + preceding titles.

    Args:
        page_texts: List of extracted PDF page texts.

    Returns:
        List of OneNotePage records.
    """
    flat = _flatten(page_texts)
    date_idx = [i for i, (ln, _) in enumerate(flat) if parse_date(ln) is not None]
    pages: list[OneNotePage] = []
    for n, di in enumerate(date_idx):
        line, section = flat[di]
        title = (
            flat[di - 1][0]
            if di >= 1 and flat[di - 1][1] == section
            else "Untitled"
        )
        end = (date_idx[n + 1] - 1) if n + 1 < len(date_idx) else len(flat)
        body = "\n".join(
            flat[j][0] for j in range(di + 1, end) if flat[j][1] == section
        )
        dt = parse_date(line)
        pages.append(OneNotePage(section, title, dt, body.strip()))
    return pages
