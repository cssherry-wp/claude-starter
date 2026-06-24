# OneNote PDF Ingestion & Weekly Decision Consolidation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the planner's deferred `.one` converter with a PDF-based OneNote ingestion — an on-demand importer that splits a notebook PDF into dated per-page notes in project folders (versioned on re-import), plus a weekly per-project "Knowledge Bank" of decision summaries backlinked to source.

**Architecture:** A pure-Python PDF parser (`onenote_pdf.py`, pypdf-backed) segments the export into per-page records; an importer (`import_onenote.py`) maps sections→projects, writes/versions notes via the filesystem (setting mtime to the page's edited date), and uses the LLM only to summarize diffs on re-import. The weekly run gathers the week's new material, attributes it to projects, and the LLM extracts decisions appended (deduped) to each `00-<Name>.md`.

**Tech Stack:** Python ≥3.11, `pypdf` (new runtime dep), existing `planner` package (`config`, `obsidian` Vault, `collectors/vault`, `synthesis`, `render_weekly`, `weekly`), stdlib `re`/`datetime`/`os`, `pytest`/`ruff`/`mypy`.

## Global Constraints

- **Python ≥3.11**, `from __future__ import annotations` atop every module, type annotations on all signatures, Google-style docstrings on public functions/classes, functions <40 lines, `ruff check .` (incl. `tests/`) + `mypy planner` clean.
- **Minimal deps:** add only `pypdf` at runtime. No pandoc, no MS Graph, no `.one` parser.
- **Dev root:** `plugins/wp-labs-planner/skills/planner-setup/scripts/` — package `planner`, tests in `…/scripts/tests/`. All commands run from the scripts dir via `uv run`. All paths below are relative to the repo root.
- **No secrets**; reuse the existing LLM backend (`synthesis.run_backend`) and Vault abstraction; the importer writes via the filesystem (it must set mtime), independent of `obsidian.mode`.
- **Vault conventions:** projects at `00-InProgress/<Name>/00-<Name>.md`, tagged `#project/<Name>`; date tag format `YYYY/MM/DD` (frontmatter tags are bare, no `#`); daily notes `zz-Sherry_Daily/YYYY-MM-DD.md`; exclude `zz-Templates`.
- **Importer CLI:** `python -m planner.import_onenote --pdf <file> [--config <path>]`.
- **OneNote PDF structure (verbatim from spec §2):** page footer `^(.+?)\s+Page\s+\d+\s*$` = section name; page-date line `^[A-Z][a-z]+day,\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s*[AP]M`; title = the non-empty line immediately above the date line; a OneNote page may span multiple PDF pages.
- **Changes-section header (verbatim):** `## Changes - #<edited YYYY/MM/DD> from #<original YYYY/MM/DD>`.
- **Resilience:** importer aborts on a `pypdf` load failure (on-demand) but skips a bad page; weekly consolidation skips a failing project and continues. A failed change-summary still advances versioning with a "summary unavailable" line.

---

## File Structure

| Path (under `…/scripts/`) | Responsibility | Task |
| --- | --- | --- |
| `planner/config.py` | Reshape `OneNoteCfg` (pdf / section_to_project / import_dir) | 1 |
| `planner/collectors/onenote.py` | **Deleted** (old `.one` converter) | 1 |
| `planner/daily.py` | Drop the daily OneNote gather step | 1 |
| `planner/onenote_pdf.py` | Pure PDF parsing → `OneNotePage` records | 2 |
| `planner/onenote_notes.py` | Note rendering + versioned-note string assembly | 3 |
| `planner/synthesis.py` | `summarize_changes` + `extract_decisions` | 4, 7 |
| `planner/import_onenote.py` | Importer entry point (map → write/version → mtime) | 5 |
| `planner/collectors/vault.py` | `attribute_material` (per-project new material) | 6 |
| `planner/render_weekly.py` | `update_knowledge_bank` (dedup, backlinks, newest-first) | 8 |
| `planner/weekly.py` | Wire knowledge-bank consolidation into the weekly run | 9 |
| `templates/prompts/{onenote_changes,decisions}.md` | Prompt templates | 4, 7 |
| `templates/config.example.yaml`, `README.md`, `SKILL.md` | Docs for the new command + config | 10 |

---

## Task 1: Reshape `OneNoteCfg` and retire the `.one` collector

**Files:**
- Modify: `…/scripts/planner/config.py` (`OneNoteCfg`, `_build_onenote`)
- Delete: `…/scripts/planner/collectors/onenote.py`, `…/scripts/tests/test_collectors_onenote.py`
- Modify: `…/scripts/planner/daily.py` (`_gather_daily`)
- Modify: `…/scripts/tests/fixtures/config_valid.yaml`, `…/scripts/tests/test_config.py`

**Interfaces:**
- Consumes: existing `Config`, `_expand`.
- Produces: `OneNoteCfg(pdf: list[str], section_to_project: dict[str, str], import_dir: str)`; `_build_onenote(o: dict[str, Any]) -> OneNoteCfg`. Removes `OneNoteCfg.files`/`converter_command` and `planner.collectors.onenote`.

- [ ] **Step 1: Update the fixture's `onenote` block**

In `tests/fixtures/config_valid.yaml`, replace the `onenote:` block with:
```yaml
onenote:
  pdf:
    - ~/OneDrive/Notebooks/AI Value Creation.pdf
  section_to_project:
    "UVEX (Hexarmor)": Hexarmor
    "Example-Infinite": Infinite
    "Warburg TA": WarburgTA
  import_dir: OneNote
```

- [ ] **Step 2: Update `test_config.py` for the new shape**

Replace the OneNote assertions in `test_loads_valid_config` (and remove any `files`/`converter_command` references) with:
```python
    assert cfg.onenote.pdf == [str(Path("~/OneDrive/Notebooks/AI Value Creation.pdf").expanduser())]
    assert cfg.onenote.section_to_project["UVEX (Hexarmor)"] == "Hexarmor"
    assert cfg.onenote.import_dir == "OneNote"
```
(Ensure `from pathlib import Path` is imported in the test.)

- [ ] **Step 3: Run config test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL (`OneNoteCfg` still has `files`/`converter_command`; new fields missing).

- [ ] **Step 4: Reshape `OneNoteCfg` + `_build_onenote`**

In `planner/config.py`, replace the `OneNoteCfg` dataclass and its builder:
```python
@dataclass
class OneNoteCfg:
    pdf: list[str]
    section_to_project: dict[str, str]
    import_dir: str


def _build_onenote(o: dict[str, Any]) -> OneNoteCfg:
    """Build the OneNote config (PDF ingestion)."""
    pdf = o.get("pdf", [])
    if isinstance(pdf, str):
        pdf = [pdf]
    return OneNoteCfg(
        pdf=[_expand(p) for p in pdf],
        section_to_project=dict(o.get("section_to_project", {})),
        import_dir=o.get("import_dir", "OneNote"),
    )
```

- [ ] **Step 5: Delete the old `.one` collector and its test**

```bash
git rm plugins/wp-labs-planner/skills/planner-setup/scripts/planner/collectors/onenote.py \
       plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_collectors_onenote.py
```

- [ ] **Step 6: Drop the OneNote step from the daily gather**

In `planner/daily.py` `_gather_daily`, remove the `onenote` import usage and the `"onenote": _safe(...)` entry. Concretely, delete this line from the returned dict:
```python
        "onenote": _safe("onenote", lambda: "\n\n".join(
            onenote.convert(p, cfg.onenote.converter_command) for p in cfg.onenote.files)),
```
and remove `onenote` from the `from planner.collectors import gdoc, gmail, onenote` import (leave `gdoc, gmail`).

- [ ] **Step 7: Run the full suite + lint + types**

Run: `uv run pytest -v && uv run ruff check . && uv run mypy planner`
Expected: all pass (onenote test gone; config test green; daily test still green — it monkeypatches `_gather_daily`).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(planner): reshape OneNoteCfg for PDF ingestion; remove .one collector"
```

---

## Task 2: `onenote_pdf.py` — pure PDF parsing

**Files:**
- Create: `…/scripts/planner/onenote_pdf.py`
- Modify: `…/scripts/pyproject.toml` (add `pypdf`)
- Test: `…/scripts/tests/test_onenote_pdf.py`

**Interfaces:**
- Produces:
  - `@dataclass OneNotePage(section: str, title: str, date: datetime.date | None, body: str)`
  - `parse_date(line: str) -> date | None`
  - `read_pdf_pages(path: str) -> list[str]` (thin pypdf wrapper)
  - `parse_pages(page_texts: list[str]) -> list[OneNotePage]`

- [ ] **Step 1: Add `pypdf` to `pyproject.toml`**

In `[project].dependencies`, add `"pypdf==5.1.0"`. Then:
```bash
cd plugins/wp-labs-planner/skills/planner-setup/scripts && uv pip install -e ".[dev]"
```

- [ ] **Step 2: Write the failing test**

`tests/test_onenote_pdf.py`:
```python
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
    assert p1.title == "Matching Architecture"
    assert p1.date == date(2026, 5, 27)
    assert "other page body" in p1.body
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_onenote_pdf.py -v`
Expected: FAIL (`ModuleNotFoundError: planner.onenote_pdf`).

- [ ] **Step 4: Write the implementation**

`planner/onenote_pdf.py`:
```python
"""Parse a OneNote PDF export into per-page records (pure over extracted text)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

_FOOTER = re.compile(r"^(.+?)\s+Page\s+\d+\s*$")
_DATE = re.compile(
    r"^[A-Z][a-z]+day,\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s*[AP]M\b"
)
_DATE_FMT = "%A, %B %d, %Y %I:%M %p"


@dataclass
class OneNotePage:
    section: str
    title: str
    date: date | None
    body: str


def parse_date(line: str) -> date | None:
    """Parse a OneNote page-date line ('Tuesday, May 26, 2026 4:25 PM') to a date."""
    s = line.strip()
    if not _DATE.match(s):
        return None
    try:
        return datetime.strptime(s, _DATE_FMT).date()
    except ValueError:
        return None


def read_pdf_pages(path: str) -> list[str]:
    """Return the extracted text of each PDF page (thin pypdf wrapper)."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    return [(page.extract_text() or "") for page in reader.pages]


def _flatten(page_texts: list[str]) -> list[tuple[str, str]]:
    """Return (line, section) for each non-blank, non-footer line; section carries fwd."""
    out: list[tuple[str, str]] = []
    section = ""
    for text in page_texts:
        lines = [ln.strip() for ln in text.splitlines()]
        for ln in lines:                       # section comes from any footer on the page
            fm = _FOOTER.match(ln)
            if fm:
                section = fm.group(1).strip()
        for ln in lines:
            if ln and not _FOOTER.match(ln):
                out.append((ln, section))
    return out


def parse_pages(page_texts: list[str]) -> list[OneNotePage]:
    """Segment extracted PDF text into OneNote pages via date lines + preceding titles."""
    flat = _flatten(page_texts)
    date_idx = [i for i, (ln, _) in enumerate(flat) if parse_date(ln) is not None]
    pages: list[OneNotePage] = []
    for n, di in enumerate(date_idx):
        line, section = flat[di]
        title = flat[di - 1][0] if di >= 1 and flat[di - 1][1] == section else "Untitled"
        end = (date_idx[n + 1] - 1) if n + 1 < len(date_idx) else len(flat)
        body = "\n".join(flat[j][0] for j in range(di + 1, end) if flat[j][1] == section)
        pages.append(OneNotePage(section, title, parse_date(line), body.strip()))
    return pages
```
> Note: content before the first date line (floating-box preamble) is intentionally dropped — it is layout noise, not page content.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_onenote_pdf.py -v`
Expected: `2 passed`.

- [ ] **Step 6: Lint, types, commit**

```bash
uv run ruff check . && uv run mypy planner
git add planner/onenote_pdf.py pyproject.toml uv.lock tests/test_onenote_pdf.py
git commit -m "feat(planner): OneNote PDF parser (section/page/date segmentation)"
```

---

## Task 3: `onenote_notes.py` — note rendering + versioned assembly

**Files:**
- Create: `…/scripts/planner/onenote_notes.py`
- Test: `…/scripts/tests/test_onenote_notes.py`

**Interfaces:**
- Consumes: `planner.onenote_pdf.OneNotePage`.
- Produces:
  - `sanitize_filename(title: str) -> str`
  - `changes_header(new: date, old: date) -> str` → `"## Changes - #YYYY/MM/DD from #YYYY/MM/DD"`
  - `render_note(page: OneNotePage, project: str | None) -> str` (frontmatter + `## Notes` body)
  - `parse_note(text: str) -> tuple[date | None, str, str]` → `(stored_date, changes_blocks, body)`
  - `versioned_note(existing: str, page: OneNotePage, project: str | None, summary: str) -> str`

- [ ] **Step 1: Write the failing test**

`tests/test_onenote_notes.py`:
```python
from __future__ import annotations

from datetime import date

from planner.onenote_pdf import OneNotePage
from planner.onenote_notes import (
    changes_header, parse_note, render_note, sanitize_filename, versioned_note,
)


def test_sanitize_filename() -> None:
    assert sanitize_filename("VIP: Tesla / Plan?") == "VIP Tesla Plan"


def test_render_note_has_frontmatter_and_body() -> None:
    page = OneNotePage("VIP", "Tesla Plan", date(2026, 5, 26), "body text")
    note = render_note(page, "VIP")
    assert note.startswith("---\n")
    assert "- 2026/05/26" in note
    assert "- project/VIP" in note
    assert "## Notes" in note
    assert note.rstrip().endswith("body text")


def test_render_note_unmapped_has_no_project_tag() -> None:
    page = OneNotePage("WP Labs", "Idea", date(2026, 5, 26), "x")
    assert "project/" not in render_note(page, None)


def test_changes_header_format() -> None:
    assert changes_header(date(2026, 6, 10), date(2026, 6, 3)) == \
        "## Changes - #2026/06/10 from #2026/06/03"


def test_parse_note_roundtrip() -> None:
    page = OneNotePage("VIP", "Tesla Plan", date(2026, 5, 26), "first body")
    note = render_note(page, "VIP")
    d, changes, body = parse_note(note)
    assert d == date(2026, 5, 26)
    assert changes == ""
    assert body.strip() == "first body"


def test_versioned_note_prepends_changes_and_replaces_body() -> None:
    page_v1 = OneNotePage("VIP", "Tesla Plan", date(2026, 5, 26), "old body")
    v1 = render_note(page_v1, "VIP")
    page_v2 = OneNotePage("VIP", "Tesla Plan", date(2026, 6, 10), "new body")
    v2 = versioned_note(v1, page_v2, "VIP", "Added decision X; revised timeline")
    assert "## Changes - #2026/06/10 from #2026/05/26" in v2
    assert "Added decision X" in v2
    assert "## Notes" in v2
    assert v2.rstrip().endswith("new body")    # body replaced with latest
    assert "old body" not in v2                # old body not kept (changelog summarizes)
    d, changes, body = parse_note(v2)
    assert d == date(2026, 6, 10)
    assert "## Changes - #2026/06/10" in changes
    assert body.strip() == "new body"
    # A second version preserves the first changelog entry (newest on top).
    page_v3 = OneNotePage("VIP", "Tesla Plan", date(2026, 6, 20), "newest body")
    v3 = versioned_note(v2, page_v3, "VIP", "Dropped Y")
    assert v3.index("#2026/06/20") < v3.index("#2026/06/10")
    assert "## Changes - #2026/06/10 from #2026/05/26" in v3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_onenote_notes.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the implementation**

`planner/onenote_notes.py`:
```python
"""Render imported OneNote pages to notes and assemble versioned (changelog) notes."""
from __future__ import annotations

import re
from datetime import date

from planner.onenote_pdf import OneNotePage

_BODY_HEADING = "## Notes"
_DATE_TAG = re.compile(r"^- (\d{4}/\d{2}/\d{2})$", re.MULTILINE)


def sanitize_filename(title: str) -> str:
    """Make a filesystem-safe note basename from a page title (no extension)."""
    cleaned = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", title)
    return re.sub(r"\s+", " ", cleaned).strip() or "Untitled"


def changes_header(new: date, old: date) -> str:
    """Return the versioning header line for a re-import diff."""
    return f"## Changes - #{new:%Y/%m/%d} from #{old:%Y/%m/%d}"


def _frontmatter(d: date | None, project: str | None) -> str:
    tags = []
    if d:
        tags.append(f"- {d:%Y/%m/%d}")
    if project:
        tags.append(f"- project/{project}")
    return "---\ntags:\n" + "\n".join(tags) + "\n---\n"


def render_note(page: OneNotePage, project: str | None) -> str:
    """Render a fresh note: frontmatter + a '## Notes' body section."""
    return _frontmatter(page.date, project) + f"{_BODY_HEADING}\n{page.body}\n"


def parse_note(text: str) -> tuple[date | None, str, str]:
    """Split a note into (stored_date, changes-blocks text, body text)."""
    stored: date | None = None
    m = _DATE_TAG.search(text.split("---", 2)[1] if text.count("---") >= 2 else text)
    if m:
        y, mo, d = (int(x) for x in m.group(1).split("/"))
        stored = date(y, mo, d)
    after_fm = text.split("---", 2)[2] if text.count("---") >= 2 else text
    if _BODY_HEADING in after_fm:
        head, body = after_fm.split(_BODY_HEADING, 1)
        return stored, head.strip(), body.strip()
    return stored, "", after_fm.strip()


def versioned_note(existing: str, page: OneNotePage, project: str | None, summary: str) -> str:
    """Prepend a dated changes block, keep prior changes, replace body with latest."""
    old_date, old_changes, _ = parse_note(existing)
    header = changes_header(page.date, old_date) if (page.date and old_date) else \
        f"## Changes - #{page.date:%Y/%m/%d}"
    block = f"{header}\n{summary.strip()}\n"
    prior = (old_changes + "\n") if old_changes else ""
    return (_frontmatter(page.date, project) + block + "\n" + prior
            + f"{_BODY_HEADING}\n{page.body}\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_onenote_notes.py -v`
Expected: `6 passed`.

- [ ] **Step 5: Lint, types, commit**

```bash
uv run ruff check . && uv run mypy planner
git add planner/onenote_notes.py tests/test_onenote_notes.py
git commit -m "feat(planner): OneNote note rendering + versioned changelog assembly"
```

---

## Task 4: `synthesis.summarize_changes` + prompt

**Files:**
- Modify: `…/scripts/planner/synthesis.py`
- Create: `…/scripts/templates/prompts/onenote_changes.md`
- Test: `…/scripts/tests/test_synthesis.py` (add a test)

**Interfaces:**
- Consumes: existing `run_backend(cfg: LlmCfg, prompt: str) -> str`, `LlmCfg`.
- Produces: `summarize_changes(cfg: LlmCfg, prompt_template: str, old: str, new: str) -> str` — fills `{old}`/`{new}` into the template, calls the backend, returns the trimmed text. On `SynthesisError` it re-raises (the importer catches and substitutes a fallback line).

- [ ] **Step 1: Write the failing test (backend mocked)**

Add to `tests/test_synthesis.py`:
```python
def test_summarize_changes_fills_and_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake(cfg, prompt):
        seen.append(prompt)
        return "  Added decision X.  "

    monkeypatch.setattr(syn, "run_backend", fake)
    cfg = LlmCfg("claude", "claude", ["-p"], "", "")
    out = syn.summarize_changes(cfg, "OLD:{old}\nNEW:{new}", "old text", "new text")
    assert out == "Added decision X."
    assert "old text" in seen[0] and "new text" in seen[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_synthesis.py::test_summarize_changes_fills_and_returns -v`
Expected: FAIL (`AttributeError: summarize_changes`).

- [ ] **Step 3: Write the implementation**

Add to `planner/synthesis.py`:
```python
def summarize_changes(cfg: LlmCfg, prompt_template: str, old: str, new: str) -> str:
    """Summarize what changed between two versions of a note's body."""
    prompt = prompt_template.replace("{old}", old).replace("{new}", new)
    return run_backend(cfg, prompt).strip()
```

- [ ] **Step 4: Write the prompt template**

`templates/prompts/onenote_changes.md`:
```markdown
You are comparing two versions of a note. Output ONLY a short Markdown bullet list
(no preamble) of the substantive changes from OLD to NEW — added/removed/revised
decisions, facts, or action items. Ignore pure reformatting. Keep it to a few bullets.

OLD:
{old}

NEW:
{new}
```

- [ ] **Step 5: Run test + suite, lint, types, commit**

```bash
uv run pytest tests/test_synthesis.py -v && uv run ruff check . && uv run mypy planner
git add planner/synthesis.py templates/prompts/onenote_changes.md tests/test_synthesis.py
git commit -m "feat(planner): synthesis.summarize_changes for re-import diffs"
```

---

## Task 5: `import_onenote.py` — importer entry point

**Files:**
- Create: `…/scripts/planner/import_onenote.py`
- Test: `…/scripts/tests/test_import_onenote.py`

**Interfaces:**
- Consumes: `config.load_config`/`Config`; `onenote_pdf.{read_pdf_pages,parse_pages,OneNotePage}`; `onenote_notes.{sanitize_filename,render_note,versioned_note,parse_note}`; `synthesis.summarize_changes`.
- Produces:
  - `target_dir(page: OneNotePage, cfg: Config) -> tuple[Path, str | None]` — `(absolute dir, project_or_None)`; project from `section_to_project`, else fallback `import_dir/<section>`.
  - `set_mtime(path: Path, d: date) -> None`
  - `import_page(page, cfg, summarize) -> str` — write/version one note; returns `"created"|"skipped"|"updated"`. `summarize` is `Callable[[str, str], str]` (injected; defaults to a `summarize_changes` closure).
  - `run_import(cfg, pdf_path, summarize) -> dict[str, int]` — counts per action.
  - `main() -> None` — `--pdf`/`--config`; reads pages, parses, runs each configured PDF.

- [ ] **Step 1: Write the failing test (filesystem; summarize stubbed)**

`tests/test_import_onenote.py`:
```python
from __future__ import annotations

import datetime as dt
from datetime import date
from pathlib import Path

from planner.config import load_config
from planner.import_onenote import import_page, target_dir
from planner.onenote_pdf import OneNotePage

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def cfg_for(tmp_path: Path):
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.onenote.section_to_project = {"UVEX (Hexarmor)": "Hexarmor"}
    cfg.onenote.import_dir = "OneNote"
    (tmp_path / "00-InProgress" / "Hexarmor").mkdir(parents=True)
    return cfg


def test_target_dir_mapped_vs_fallback(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    d_map, proj = target_dir(OneNotePage("UVEX (Hexarmor)", "T", date(2026, 5, 26), ""), cfg)
    assert proj == "Hexarmor" and d_map.as_posix().endswith("00-InProgress/Hexarmor")
    d_fb, proj2 = target_dir(OneNotePage("WP Labs", "T", date(2026, 5, 26), ""), cfg)
    assert proj2 is None and d_fb.as_posix().endswith("OneNote/WP Labs")


def test_import_page_created_then_skipped_then_updated(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    page = OneNotePage("UVEX (Hexarmor)", "Harlo testing", date(2026, 5, 26), "v1 body")
    assert import_page(page, cfg, lambda old, new: "summary") == "created"
    note = tmp_path / "00-InProgress" / "Hexarmor" / "Harlo testing.md"
    assert note.is_file()
    assert "v1 body" in note.read_text()
    # mtime set to the page date (2026-05-26).
    assert dt.date.fromtimestamp(note.stat().st_mtime) == date(2026, 5, 26)
    # Same date again -> skipped.
    assert import_page(page, cfg, lambda old, new: "summary") == "skipped"
    # Newer date -> updated with a prepended changes block + replaced body.
    newer = OneNotePage("UVEX (Hexarmor)", "Harlo testing", date(2026, 6, 10), "v2 body")
    assert import_page(newer, cfg, lambda old, new: "Added X") == "updated"
    text = note.read_text()
    assert "## Changes - #2026/06/10 from #2026/05/26" in text
    assert "Added X" in text and "v2 body" in text
    assert dt.date.fromtimestamp(note.stat().st_mtime) == date(2026, 6, 10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_import_onenote.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the implementation**

`planner/import_onenote.py`:
```python
"""On-demand importer: split a OneNote PDF into dated, versioned per-page notes."""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from planner.config import Config, load_config
from planner.onenote_notes import parse_note, render_note, sanitize_filename, versioned_note
from planner.onenote_pdf import OneNotePage, parse_pages, read_pdf_pages
from planner.synthesis import summarize_changes

log = logging.getLogger(__name__)
Summarize = Callable[[str, str], str]


def target_dir(page: OneNotePage, cfg: Config) -> tuple[Path, str | None]:
    """Return (absolute target dir, project name or None) for a page."""
    root = Path(cfg.vault.path)
    project = cfg.onenote.section_to_project.get(page.section)
    if project:
        return root / cfg.vault.projects_dir / project, project
    log.warning("OneNote section %r unmapped; importing to %s/", page.section, cfg.onenote.import_dir)
    return root / cfg.onenote.import_dir / page.section, None


def set_mtime(path: Path, d: date) -> None:
    """Set a note's mtime to the page's edited date (noon, to avoid TZ edges)."""
    ts = datetime(d.year, d.month, d.day, 12, 0).timestamp()
    os.utime(path, (ts, ts))


def import_page(page: OneNotePage, cfg: Config, summarize: Summarize) -> str:
    """Write or version one page note. Returns 'created' | 'skipped' | 'updated'."""
    directory, project = target_dir(page, cfg)
    directory.mkdir(parents=True, exist_ok=True)
    note = directory / f"{sanitize_filename(page.title)}.md"
    if not note.exists():
        note.write_text(render_note(page, project), encoding="utf-8")
        if page.date:
            set_mtime(note, page.date)
        return "created"
    stored_date, _, _ = parse_note(note.read_text(encoding="utf-8"))
    if page.date and stored_date and page.date <= stored_date:
        return "skipped"
    existing = note.read_text(encoding="utf-8")
    _, _, old_body = parse_note(existing)
    try:
        summary = summarize(old_body, page.body)
    except Exception as exc:  # noqa: BLE001 — versioning must still advance
        log.warning("change summary failed for %s: %s", note.name, exc)
        summary = "_change summary unavailable_"
    note.write_text(versioned_note(existing, page, project, summary), encoding="utf-8")
    if page.date:
        set_mtime(note, page.date)
    return "updated"


def run_import(cfg: Config, pdf_path: str, summarize: Summarize) -> dict[str, int]:
    """Import every page of one PDF; return action counts."""
    counts = {"created": 0, "skipped": 0, "updated": 0}
    for page in parse_pages(read_pdf_pages(pdf_path)):
        try:
            counts[import_page(page, cfg, summarize)] += 1
        except OSError as exc:  # skip a bad page, keep going
            log.warning("failed to import page %r: %s", page.title, exc)
    return counts


def main() -> None:
    """CLI: python -m planner.import_onenote --pdf <file> [--config PATH]."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.environ.get("PLANNER_CONFIG", "config.yaml"))
    parser.add_argument("--pdf", action="append", help="PDF path (repeatable); defaults to config")
    args = parser.parse_args()
    cfg = load_config(args.config)
    pdfs = args.pdf or cfg.onenote.pdf
    summarize: Summarize = lambda old, new: summarize_changes(
        cfg.llm, _load_prompt("onenote_changes.md"), old, new)
    for pdf in pdfs:
        print(pdf, run_import(cfg, pdf, summarize))


def _load_prompt(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / "templates" / "prompts" / name).read_text()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_import_onenote.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Suite, lint, types, commit**

```bash
uv run pytest -v && uv run ruff check . && uv run mypy planner
git add planner/import_onenote.py tests/test_import_onenote.py
git commit -m "feat(planner): import_onenote entry point (map, write, version, mtime)"
```

---

## Task 6: `attribute_material` — per-project new material

**Files:**
- Modify: `…/scripts/planner/collectors/vault.py`
- Test: `…/scripts/tests/test_collectors_vault.py` (add tests)

**Interfaces:**
- Consumes: existing `recent_notes(vault, cfg, today, repo_path)`, `RecentNote`, `list_projects`, `Vault`, `Config`.
- Produces:
  - `@dataclass Material(project: str, note_path: str, header: str, text: str)`
  - `attribute_material(vault: Vault, cfg: Config, today: date, repo_path: str | None) -> dict[str, list[Material]]` — over recent notes (past week + edited; the existing recency window), attribute each `### …`/`## …` section to a project when it contains a `#project/<Name>` tag or a `[[00-<Name>]]` link, or when the note resides in `00-InProgress/<Name>/`. The `header` is the nearest enclosing `##`/`###` heading text (or `""`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_collectors_vault.py`:
```python
from planner.collectors.vault import attribute_material, Material


def test_attribute_material_by_tag_and_folder(tmp_path: Path) -> None:
    v = build_vault(tmp_path)  # existing helper: makes 00-InProgress/A5 + a daily note
    # A daily note with a project-tagged section.
    daily = tmp_path / "zz-Sherry_Daily" / "2026-06-23.md"
    daily.write_text("## Notes\n### Harlo testing #project/Hexarmor\n- decided to ship\n")
    # An imported page-note inside a project folder.
    (tmp_path / "00-InProgress" / "Hexarmor").mkdir(parents=True)
    (tmp_path / "00-InProgress" / "Hexarmor" / "Page.md").write_text(
        "---\ntags:\n- 2026/06/23\n- project/Hexarmor\n---\n## Notes\nchose vendor X\n")
    cfg = cfg_for(tmp_path)
    mats = attribute_material(v, cfg, date(2026, 6, 23), repo_path=None)
    hexar = mats.get("Hexarmor", [])
    assert any("decided to ship" in m.text and m.header == "Harlo testing #project/Hexarmor"
               for m in hexar)
    assert any(m.note_path.endswith("Hexarmor/Page.md") for m in hexar)
```
(Reuse the file's existing `build_vault`/`cfg_for` helpers; ensure `Material` is importable.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collectors_vault.py::test_attribute_material_by_tag_and_folder -v`
Expected: FAIL (`ImportError: attribute_material`).

- [ ] **Step 3: Write the implementation**

Add to `planner/collectors/vault.py`:
```python
import re

_PROJECT_TAG = re.compile(r"#project/([A-Za-z0-9_-]+)")
_PROJECT_LINK = re.compile(r"\[\[00-([A-Za-z0-9_ -]+?)(?:[#|\]])")


@dataclass
class Material:
    project: str
    note_path: str
    header: str
    text: str


def _project_for_folder(path: str, cfg: Config) -> str | None:
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == cfg.vault.projects_dir:
        return parts[1]
    return None


def attribute_material(vault: Vault, cfg: Config, today: date,
                       repo_path: str | None) -> dict[str, list[Material]]:
    """Attribute recent notes' sections to projects via tags / links / folder."""
    out: dict[str, list[Material]] = {}
    valid = {p.name for p in list_projects(vault, cfg)}
    for note in recent_notes(vault, cfg, today, repo_path):
        folder_project = _project_for_folder(note.path, cfg)
        header = ""
        for line in note.content.splitlines():
            if line.startswith("#") and " " in line[:4] + " ":
                if line.lstrip("#").startswith(" "):
                    header = line.lstrip("# ").rstrip()
            tagged = {m for m in _PROJECT_TAG.findall(line)}
            tagged |= {m.strip() for m in _PROJECT_LINK.findall(line)}
            targets = (tagged & valid) or ({folder_project} if folder_project in valid else set())
            for proj in targets:
                out.setdefault(proj, []).append(
                    Material(proj, note.path, header, line.strip()))
    return out
```
> `recent_notes` already bounds the window to the past week + git/mtime-recent notes, satisfying "new material only." Dedup of resulting decisions happens in the knowledge bank (Task 8).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collectors_vault.py -v`
Expected: all pass (existing + new).

- [ ] **Step 5: Lint, types, commit**

```bash
uv run ruff check . && uv run mypy planner
git add planner/collectors/vault.py tests/test_collectors_vault.py
git commit -m "feat(planner): attribute_material maps recent material to projects"
```

---

## Task 7: `synthesis.extract_decisions` + prompt

**Files:**
- Modify: `…/scripts/planner/synthesis.py`
- Create: `…/scripts/templates/prompts/decisions.md`
- Test: `…/scripts/tests/test_synthesis.py` (add a test)

**Interfaces:**
- Consumes: `run_backend`, `extract_json`, `LlmCfg`.
- Produces: `extract_decisions(cfg: LlmCfg, prompt_template: str, project: str, materials: list[dict]) -> list[dict]` — each input material is `{"note": path, "header": str, "text": str}`; returns a list of `{"decision": str, "note": path, "header": str}`. Fills `{project}`/`{materials}` (materials as JSON), calls the backend, parses JSON via a tolerant wrapper, returns `result["decisions"]` (or `[]`).

- [ ] **Step 1: Write the failing test (backend mocked)**

Add to `tests/test_synthesis.py`:
```python
def test_extract_decisions_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    canned = json.dumps({"decisions": [
        {"decision": "Ship Harlo to beta", "note": "zz-Sherry_Daily/2026-06-23.md",
         "header": "Harlo testing #project/Hexarmor"}]})
    monkeypatch.setattr(syn, "run_backend", lambda cfg, prompt: canned)
    cfg = LlmCfg("claude", "claude", ["-p"], "", "")
    out = syn.extract_decisions(cfg, "P:{project}\nM:{materials}", "Hexarmor",
                                [{"note": "x.md", "header": "h", "text": "t"}])
    assert out == [{"decision": "Ship Harlo to beta",
                    "note": "zz-Sherry_Daily/2026-06-23.md",
                    "header": "Harlo testing #project/Hexarmor"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_synthesis.py::test_extract_decisions_parses -v`
Expected: FAIL (`AttributeError: extract_decisions`).

- [ ] **Step 3: Write the implementation**

Add to `planner/synthesis.py`:
```python
def extract_decisions(cfg: LlmCfg, prompt_template: str, project: str,
                      materials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract decision summaries (with source note/header) from project material."""
    prompt = (prompt_template.replace("{project}", project)
              .replace("{materials}", json.dumps(materials, indent=2, default=str)))
    result = extract_json(run_backend(cfg, prompt))
    decisions = result.get("decisions", [])
    return decisions if isinstance(decisions, list) else []
```

- [ ] **Step 4: Write the prompt template**

`templates/prompts/decisions.md`:
```markdown
You are maintaining a decision log for the project "{project}". From the MATERIALS
below (each item has note/header/text), extract only HIGH-LEVEL decisions that were
made — not tasks, notes, or status. Output ONLY a JSON object:

{
  "decisions": [
    {"decision": "<one-sentence decision>", "note": "<source note path>",
     "header": "<the item's header, verbatim, or empty>"}
  ]
}

Use the note/header from the source item the decision came from. No prose, no fences.

MATERIALS:
{materials}
```

- [ ] **Step 5: Run test + suite, lint, types, commit**

```bash
uv run pytest tests/test_synthesis.py -v && uv run ruff check . && uv run mypy planner
git add planner/synthesis.py templates/prompts/decisions.md tests/test_synthesis.py
git commit -m "feat(planner): synthesis.extract_decisions for the knowledge bank"
```

---

## Task 8: `render_weekly.update_knowledge_bank`

**Files:**
- Modify: `…/scripts/planner/render_weekly.py`
- Test: `…/scripts/tests/test_render_weekly.py` (add tests)

**Interfaces:**
- Consumes: existing `update_project_section(content, heading, dated_line, entry_date)` pattern (for insertion style).
- Produces:
  - `decision_bullet(decision: dict) -> str` → `- <decision> — [[<note-stem>#<header>]]` (or `[[<note-stem>]]` when no header).
  - `update_knowledge_bank(content: str, decisions: list[dict]) -> str` — append only bullets whose normalized decision text isn't already present, under a `## Knowledge Bank` section (created before `## TODO` if absent), newest-first, preserving existing entries.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render_weekly.py`:
```python
from planner.render_weekly import decision_bullet, update_knowledge_bank


def test_decision_bullet_links_to_header() -> None:
    b = decision_bullet({"decision": "Ship beta", "note": "zz-Sherry_Daily/2026-06-23.md",
                         "header": "Harlo testing"})
    assert b == "- Ship beta — [[2026-06-23#Harlo testing]]"
    b2 = decision_bullet({"decision": "Pick X", "note": "00-InProgress/VIP/Page.md", "header": ""})
    assert b2 == "- Pick X — [[Page]]"


def test_update_knowledge_bank_appends_dedups_newest_first() -> None:
    content = "# VIP\n## Summary\n\n## TODO\n- [ ] x\n"
    d1 = [{"decision": "Ship beta", "note": "a.md", "header": "H"}]
    out1 = update_knowledge_bank(content, d1)
    assert "## Knowledge Bank" in out1
    assert "- Ship beta — [[a#H]]" in out1
    assert out1.index("## Knowledge Bank") < out1.index("## TODO")
    # Re-run with one duplicate + one new -> only the new one is added, newest on top.
    d2 = [{"decision": "Ship beta", "note": "a.md", "header": "H"},
          {"decision": "Drop Y", "note": "b.md", "header": "H2"}]
    out2 = update_knowledge_bank(out1, d2)
    assert out2.count("Ship beta") == 1
    assert "Drop Y" in out2
    assert out2.index("Drop Y") < out2.index("Ship beta")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_render_weekly.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Write the implementation**

Add to `planner/render_weekly.py`:
```python
from pathlib import PurePosixPath


def decision_bullet(decision: dict) -> str:
    """Render one knowledge-bank bullet with an Obsidian backlink to its source."""
    stem = PurePosixPath(decision.get("note", "")).stem
    header = (decision.get("header") or "").strip()
    link = f"[[{stem}#{header}]]" if header else f"[[{stem}]]"
    return f"- {decision.get('decision', '').strip()} — {link}"


def update_knowledge_bank(content: str, decisions: list[dict]) -> str:
    """Append new decision bullets under '## Knowledge Bank', deduped, newest-first."""
    marker = "## Knowledge Bank"
    existing = content
    fresh = [decision_bullet(d) for d in decisions]
    fresh = [b for b in fresh if b.rsplit(" — ", 1)[0] not in existing]
    if not fresh:
        return content
    block = "\n".join(reversed(fresh))  # newest-first within this batch
    if marker in content:
        idx = content.index(marker) + len(marker)
        return content[:idx] + "\n" + block + content[idx:]
    todo = content.find("## TODO")
    at = todo if todo != -1 else len(content)
    return content[:at] + f"{marker}\n{block}\n\n" + content[at:]
```
> Dedup is by the bullet's text portion (before ` — `), so the same decision isn't re-added across weekly runs even if its link differs.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_render_weekly.py -v`
Expected: all pass.

- [ ] **Step 5: Lint, types, commit**

```bash
uv run ruff check . && uv run mypy planner
git add planner/render_weekly.py tests/test_render_weekly.py
git commit -m "feat(planner): weekly Knowledge Bank update (dedup, backlinks, newest-first)"
```

---

## Task 9: Wire knowledge-bank consolidation into the weekly run

**Files:**
- Modify: `…/scripts/planner/weekly.py`
- Test: `…/scripts/tests/test_entrypoints.py` (add a test)

**Interfaces:**
- Consumes: `attribute_material` (Task 6), `extract_decisions` (Task 7), `update_knowledge_bank` (Task 8), existing `make_vault`, `list_projects`, `is_git_repo`, `_load_prompt`.
- Produces: `consolidate_knowledge(vault, cfg, projects, today) -> list[str]` — for each project with attributed material, extract decisions and update its `00-<Name>.md` in place; returns the list of project index paths touched. Wired into `run_weekly` after the status/timeline updates (before the commit), and its touched paths added to the commit set. Per-project failures are caught and logged.

- [ ] **Step 1: Write the failing test (collaborators stubbed)**

Add to `tests/test_entrypoints.py`:
```python
def test_consolidate_knowledge_updates_index(tmp_path, monkeypatch) -> None:
    proj = tmp_path / "00-InProgress" / "VIP"
    proj.mkdir(parents=True)
    (proj / "00-VIP.md").write_text("# VIP\n## Summary\n## TODO\n")
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    import planner.weekly as wk
    from planner.collectors.vault import Material, Project
    from planner.obsidian import FilesystemVault
    monkeypatch.setattr(wk, "attribute_material",
                        lambda v, c, t, r: {"VIP": [Material("VIP", "a.md", "H", "decided X")]})
    monkeypatch.setattr(wk, "extract_decisions",
                        lambda cfg, tmpl, project, materials:
                        [{"decision": "Do X", "note": "a.md", "header": "H"}])
    v = FilesystemVault(str(tmp_path))
    projects = [Project("VIP", "00-InProgress/VIP/00-VIP.md", (proj / "00-VIP.md").read_text())]
    touched = wk.consolidate_knowledge(v, cfg, projects, date(2026, 6, 26))
    body = (proj / "00-VIP.md").read_text()
    assert "## Knowledge Bank" in body and "Do X" in body and "[[a#H]]" in body
    assert any("00-VIP.md" in p for p in touched)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_entrypoints.py::test_consolidate_knowledge_updates_index -v`
Expected: FAIL (`AttributeError: consolidate_knowledge`).

- [ ] **Step 3: Write the implementation**

In `planner/weekly.py`, add imports and the function, and call it from `run_weekly`:
```python
from planner.collectors.vault import attribute_material, list_projects
from planner.render_weekly import update_knowledge_bank
from planner.synthesis import extract_decisions


def consolidate_knowledge(vault, cfg, projects, today):  # type: ignore[no-untyped-def]
    """Update each project's ## Knowledge Bank from this week's attributed material."""
    repo = cfg.vault.path if is_git_repo(cfg.vault.path) else None
    by_project = attribute_material(vault, cfg, today, repo)
    prompt = _load_prompt("decisions.md")
    touched: list[str] = []
    for proj in projects:
        mats = by_project.get(proj.name, [])
        if not mats:
            continue
        try:
            decisions = extract_decisions(
                cfg.llm, prompt, proj.name,
                [{"note": m.note_path, "header": m.header, "text": m.text} for m in mats])
            content = vault.read(proj.path)
            vault.write(proj.path, update_knowledge_bank(content, decisions))
            touched.append(proj.path)
        except Exception as exc:  # noqa: BLE001 — one project must not abort the run
            log.warning("knowledge bank update failed for %s: %s", proj.name, exc)
    return touched
```
Then in `run_weekly`, after the existing `render_weekly(...)` call and before the commit, add:
```python
    touched += consolidate_knowledge(vault, cfg, projects, gen_day)
```
(`projects` is already in scope from `_gather_weekly`; `touched` is the existing list of paths the run committed.)

- [ ] **Step 4: Run test + suite, lint, types**

Run: `uv run pytest -v && uv run ruff check . && uv run mypy planner`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add planner/weekly.py tests/test_entrypoints.py
git commit -m "feat(planner): weekly run consolidates per-project Knowledge Bank"
```

---

## Task 10: Docs — config example, README, setup skill

**Files:**
- Modify: `…/scripts/templates/config.example.yaml`
- Modify: `plugins/wp-labs-planner/README.md`
- Modify: `plugins/wp-labs-planner/skills/planner-setup/SKILL.md`

**Interfaces:** none (docs).

- [ ] **Step 1: Update `config.example.yaml`**

Replace the `onenote:` block with the new shape + comments:
```yaml
onenote:
  # PDF export(s) of your OneNote notebook (File > Export / Print to PDF).
  pdf:
    - ~/OneDrive/Notebooks/AI Value Creation.pdf
  # Map OneNote section names (from the page footer) to project folder names.
  # Unmapped sections import into <import_dir>/<Section>/.
  section_to_project:
    "UVEX (Hexarmor)": Hexarmor
    "Example-Infinite": Infinite
    "Warburg TA": WarburgTA
  import_dir: OneNote
```

- [ ] **Step 2: Update `README.md`**

Add an "Importing OneNote" section: export the notebook to PDF; set `onenote.pdf` + `section_to_project`; run `python -m planner.import_onenote --pdf "<file>"`; explain per-page notes land in project folders (unmapped → `OneNote/<Section>/`), carry the page's edited date (frontmatter tag + file mtime), and that re-importing a newer export prepends a `## Changes - #<new> from #<old>` block. Note the weekly run grows each project's `## Knowledge Bank` from the week's material. Remove any mention of `.one`/`converter_command`.

- [ ] **Step 3: Update `SKILL.md`**

In `planner-setup`, replace the OneNote-converter bullet with: "OneNote: export the notebook to PDF, set `onenote.pdf` + `onenote.section_to_project`, and run `python -m planner.import_onenote` to import pages into project folders." Drop the converter-on-PATH status check.

- [ ] **Step 4: Validate + final suite**

```bash
python3 -c "import yaml; yaml.safe_load(open('plugins/wp-labs-planner/skills/planner-setup/scripts/templates/config.example.yaml')); print('yaml ok')"
cd plugins/wp-labs-planner/skills/planner-setup/scripts && uv run pytest -q && uv run ruff check . && uv run mypy planner
```
Expected: `yaml ok`; suite green; lint/types clean.

- [ ] **Step 5: Commit**

```bash
git add plugins/wp-labs-planner
git commit -m "docs(planner): OneNote PDF import + Knowledge Bank setup"
```

---

## Self-Review

**1. Spec coverage**

| Spec section | Task |
| --- | --- |
| §3 PDF parse (footer/date/title/body, continuation) | 2 |
| §3 section→project map + fallback folder | 5 (`target_dir`) |
| §3 per-page note: filename, frontmatter date tag, `#project`, mtime | 3, 5 |
| §3 idempotency: new/skip/newer→prepended `## Changes - #new from #old`, body replaced | 3 (`versioned_note`), 5 (`import_page`) |
| §4 sources: imported pages + edited notes + daily notes, per-project attribution | 6 |
| §4 incremental "new material" (recency window) | 6 (via `recent_notes`) |
| §4 `## Knowledge Bank`, backlinks, dedup, newest-first, before `## TODO` | 8 |
| §4 runs in the weekly run | 9 |
| §5 config: drop files/converter_command; add pdf/section_to_project/import_dir | 1, 10 |
| §6 remove `.one` collector; drop daily OneNote step; module layout | 1, 2, 3, 5 |
| §6 `summarize_changes`, `extract_decisions` | 4, 7 |
| §7 error handling (pypdf abort, per-page skip, summary fallback, per-project skip) | 5, 9 |
| §8 testing | every task |

No gaps.

**2. Placeholder scan:** every code step contains complete code; no TBD/"handle errors"/"similar to". §9 open items (pypdf-vs-pdfminer, sanitization specifics) are resolved concretely in the plan (pypdf; `sanitize_filename` regex).

**3. Type consistency:** `OneNotePage(section,title,date,body)` is produced in Task 2 and consumed unchanged in 3/5. `Material(project,note_path,header,text)` (Task 6) → fed to `extract_decisions` as `{"note","header","text"}` dicts (Tasks 7/9) and decisions returned as `{"decision","note","header"}` (Tasks 7/8). `target_dir`/`import_page`/`run_import` signatures match between Task 5 and its test. `update_knowledge_bank(content, decisions)` and `decision_bullet(decision)` match between Tasks 8 and 9. `summarize_changes`/`extract_decisions` signatures match synthesis (4/7) and callers (5/9).
