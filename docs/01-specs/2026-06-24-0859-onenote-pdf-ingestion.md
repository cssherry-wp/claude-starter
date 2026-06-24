# wp-labs-planner — OneNote PDF Ingestion & Weekly Decision Consolidation

**Status:** Draft for review
**Date:** 2026-06-24
**Author:** Sherry Zhou
**Supersedes:** §8 (and the OneNote parts of §3/§6/§7) of
`docs/01-specs/2026-06-23-1738-wp-labs-planner.md`.

## 1. Summary

The planner's OneNote source is **not** raw `.one` binary files. The notebook is
exported to **PDF** (OneNote's print/export), and that PDF is ingested in two ways:

- **`import-onenote` (on-demand):** split the notebook PDF into one Markdown note per
  OneNote **page**, written into the matching **project** folder, each note carrying the
  page's **correct edited date**. Re-importing a newer export prepends a summarized
  changelog rather than overwriting.
- **Weekly decision consolidation (in the weekly run):** for each project, summarize the
  decisions captured in its page-notes into a growing **`## Knowledge Bank`** in the
  project's `00-<Name>.md` index, each decision backlinked to the page/header where it
  was made.

This removes the deferred `.one` converter risk entirely (the `.one`/`converter_command`
approach in the prior spec is dropped — input is a PDF, parsed in pure Python).

## 2. Why PDF (context)

Inspecting the real export (`OneNote/AI Value Creation.pdf`, 86 pages) showed a reliable,
pure-Python-parseable structure:

- Each PDF page has a footer `\<section\> Page \<N\>` — the **OneNote section** name
  (e.g. `VIP`, `UVEX (Hexarmor)`, `SDLC`). Sections correspond to the user's projects.
- Each OneNote **page** prints its **title** immediately followed by a **date line**
  (`Tuesday, May 26, 2026 4:25 PM`). A OneNote page may span multiple PDF pages; the
  sample has ~34 page-date lines across 86 PDF pages.

The mature `.one` tooling (`one2html` etc.) is therefore unnecessary; `pypdf` text
extraction over this structure is sufficient and dependency-light.

## 3. Component A — PDF importer

**Entry point:** `python -m planner.import_onenote --pdf <file> [--config <path>]`

**Parsing (pypdf, pure-Python, new runtime dep):** walk PDF pages in document order.
- **Section:** match the footer `^\s*(.+?)\s+Page\s+\d+\s*$`; footer lines are stripped
  from page content. The current section carries forward until the footer name changes.
- **Page boundary:** the OneNote date line, matched by
  `^[A-Z][a-z]+day,\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s*[AP]M`.
  Each match starts a new OneNote page. The **title** is the nearest non-empty line
  immediately above the date line. The **body** is every line after the date line up to
  the next date line (across PDF-page boundaries), with footers and page-number lines
  removed. Content before the first date line in a section attaches to that section's
  first page.
- Pages with no detectable date line are merged into the preceding page's body
  (continuation), since OneNote pages span multiple PDF pages.

**Section → project mapping:**
- `onenote.section_to_project` (config): explicit map, e.g.
  `"UVEX (Hexarmor)": Hexarmor`, `"Example-Infinite": Infinite`, `"Warburg TA": WarburgTA`.
- Sections present in the map → `00-InProgress/<Project>/`.
- Sections **not** in the map → fallback `onenote.import_dir/<Section>/` (default
  `OneNote/<Section>/`) so nothing is lost; logged as a warning.

**Per-page note output:** `…/<sanitized-title>.md` where the dir is the project folder or
the fallback folder.
- Filename: title sanitized for the filesystem; on collision within a folder, suffix the
  edited date.
- Frontmatter: the vault date-tag convention — `tags: [\<edited #YYYY/MM/DD\>]` plus
  `#project/<Name>` for project-mapped pages.
- **File mtime is set to the page's edited date** so "correct edited date" holds and the
  planner's recency (mtime/git) and Dataview see the right date.
- Body: the extracted page content.

**Idempotency / versioning (re-import of a newer export):** filename is the stable page
identity. On re-import:
- **New page** (no existing note) → write fresh.
- **Unchanged date** (page's date ≤ stored date) → skip.
- **Newer date** → the synthesizer analyzes old body vs new body and writes a
  human-readable change summary; that summary is **prepended** to the note as a section
  headed exactly:
  `## Changes - #<edited YYYY/MM/DD> from #<original YYYY/MM/DD>`
  (both dates rendered as `#YYYY/MM/DD` tags). The note **body below is replaced with the
  latest version**; prior `## Changes …` sections are preserved, newest on top, so the
  note carries a running changelog with a current body. Frontmatter date + file mtime
  update to the new edited date.

**Resilience:** a `pypdf` load failure warns and aborts the import (it is on-demand, not
mid-daily). A malformed/undetectable page logs a warning and is skipped; the rest import.

## 4. Component B — Weekly decision knowledge-bank

Runs inside `python -m planner.weekly`, after project status/timeline updates. For each
project:
- Gather the project's page-notes (those under `00-InProgress/<Project>/`, excluding the
  `00-<Name>.md` index itself).
- **Synthesis** extracts **high-level summaries of decisions made**, each with the source
  note and its nearest enclosing header.
- Append to a growing **`## Knowledge Bank`** section in `00-<Name>.md`, one bullet per
  decision: `- <decision summary> — [[<note>#<header>]]` (header-level Obsidian backlink;
  page-level `[[<note>]]` when no header applies).
- **Growing / dedup:** only decisions not already present are added (dedup by normalized
  summary text); existing entries are preserved; newest on top — the same in-place
  section-update mechanism used for `## Status` / `## Timeline`. The section is created
  before `## TODO` if absent.

## 5. Config changes

In `config.yaml`, the `onenote` block changes:
- **Removed:** `files` (list of `.one` paths), `converter_command`.
- **Added:** `pdf` (path to the notebook PDF, or a list of PDFs); `section_to_project`
  (map of OneNote section name → project folder name); `import_dir` (fallback root for
  unmapped sections, default `OneNote`).

## 6. Integration with the existing planner

- The `.one` collector (`planner/collectors/onenote.py` `convert()` + `converter_command`)
  is **removed**, along with its config and tests.
- The **daily** run drops its dedicated OneNote step. Imported page-notes carry correct
  mtimes, so the existing recent-notes machinery surfaces recently-edited OneNote content
  into the daily note's context without a separate per-run PDF parse.
- New module layout (under the planner package):
  - `planner/onenote_pdf.py` — PDF parsing: section/page segmentation, title/date/body
    extraction (pure functions over extracted text; pypdf isolated to a thin reader).
  - `planner/import_onenote.py` — entry point: parse → map → write/version notes → set
    mtime; orchestrates the synthesizer for the change summary.
  - `planner/render_weekly.py` — extended with the `## Knowledge Bank` update (reusing
    `update_project_section`-style insertion).
  - `planner/synthesis.py` — add `summarize_changes(old, new)` and
    `extract_decisions(project_notes)` prompts/functions.

## 7. Error handling

- Importer: `pypdf` failure → warn + non-zero exit (on-demand). Per-page parse failure →
  warn + skip page. Section unmapped → fallback folder + warn. Synthesis failure on a
  change summary → fall back to a literal note that the page changed (record the dated
  `## Changes` header with a "summary unavailable" line) so versioning still advances.
- Weekly consolidation: synthesis failure for a project → warn + skip that project's
  knowledge-bank update; the rest of the weekly run proceeds.

## 8. Testing

- **PDF parsing** (`onenote_pdf.py`) over a small fixture (a hand-built text fixture
  mirroring the footer + title + date-line + multi-PDF-page-span structure): section
  detection, page segmentation, title↔date pairing, footer/page-number stripping,
  continuation merging.
- **Importer:** section→project mapping + fallback folder; filename sanitize + collision;
  frontmatter date tag + `#project/<Name>`; file mtime set to the edited date; re-import
  cases — new / unchanged-skip / newer → prepended `## Changes - #<new> from #<old>` with
  a mocked synthesis summary and body replaced; prior changelog preserved newest-first.
- **Knowledge bank:** mocked synthesis → bullets with header-level backlinks; dedup
  (no duplicate decisions on re-run); newest-first; section created before `## TODO`.
- External PDF/LLM are real-file fixtures / mocked subprocess respectively (no network).

## 9. Open items for planning

- Exact `pypdf` vs `pdfminer.six` choice (start with `pypdf`; revisit only if title/date
  pairing proves unreliable on more PDFs).
- Title-sanitization rules and collision policy specifics.
- Whether `section_to_project` should also accept a normalized-name fallback before the
  import_dir fallback (kept out for now — explicit map + import_dir is unambiguous).
