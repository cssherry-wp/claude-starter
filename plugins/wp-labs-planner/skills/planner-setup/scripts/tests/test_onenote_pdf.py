from __future__ import annotations

from datetime import date

from planner.onenote_pdf import OneNotePage, parse_date, parse_pages

# Two PDF "pages" of extracted text; page 2 is a continuation of the same section.
PDF_PAGE_1 = (
    "Vermont Information Processing (VIP)\n"
    "Tuesday, May 26, 2026 4:25 PM\n"
    "First body line\n"
    "Second body line\n"
    "   VIP Page 1    \n"
)
PDF_PAGE_2 = (
    "continued body line\n"
    "Matching Architecture\n"
    "Wednesday, May 27, 2026 10:55 AM\n"
    "other page body\n"
    "   VIP Page 2    \n"
)


def test_parse_date_valid_and_invalid() -> None:
    assert parse_date("Tuesday, May 26, 2026 4:25 PM") == date(2026, 5, 26)
    assert parse_date("not a date") is None
    assert parse_date("First body line") is None
    assert parse_date("Tuesday, May 26, 2026 4:25 PM and extra") is None


def test_parse_pages_segments_titles_dates_bodies() -> None:
    pages = parse_pages([PDF_PAGE_1, PDF_PAGE_2])
    assert len(pages) == 2
    p0, p1 = pages
    assert isinstance(p0, OneNotePage)
    assert p0.section == "VIP"
    assert p0.title == "Vermont Information Processing (VIP)"
    assert p0.date == date(2026, 5, 26)
    assert "First body line" in p0.body and "Second body line" in p0.body
    assert "continued body line" in p0.body          # spans the PDF-page boundary
    assert "VIP Page 1" not in p0.body                 # footer stripped
    assert "Matching Architecture" not in p0.body      # next page's title excluded
    assert p1.section == "VIP"
    assert p1.title == "Matching Architecture"
    assert p1.date == date(2026, 5, 27)
    assert "other page body" in p1.body


def test_parse_pages_handles_section_change() -> None:
    pg1 = ("Tesla Plan\nTuesday, May 26, 2026 4:25 PM\nvip body\n   VIP Page 1    \n")
    pg2 = ("CI Setup\nWednesday, May 27, 2026 9:00 AM\nsdlc body\n   SDLC Page 1    \n")
    pages = parse_pages([pg1, pg2])
    assert [p.section for p in pages] == ["VIP", "SDLC"]
    assert pages[1].title == "CI Setup"
    assert "sdlc body" in pages[1].body
    assert "vip body" not in pages[1].body   # same-section body filter
