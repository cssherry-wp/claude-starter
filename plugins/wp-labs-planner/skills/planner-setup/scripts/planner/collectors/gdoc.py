"""Google Doc collector: extract todos as plain-text Markdown."""
from __future__ import annotations

from typing import Any


def fetch_todos(docs_service: Any, doc_id: str) -> str:
    """Return the document body text (one line per paragraph) as Markdown.

    Args:
        docs_service: Google Docs API service object.
        doc_id: The document ID to fetch.

    Returns:
        Plain text Markdown with one line per paragraph.
    """
    doc = docs_service.documents().get(documentId=doc_id).execute()
    lines: list[str] = []
    for element in doc.get("body", {}).get("content", []):
        para = element.get("paragraph")
        if not para:
            continue
        text = "".join(
            run.get("textRun", {}).get("content", "")
            for run in para.get("elements", [])
        ).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)
