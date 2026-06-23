from __future__ import annotations

from planner.collectors.gdoc import fetch_todos


class FakeDocs:
    def __init__(self, doc: dict) -> None:
        self._doc = doc

    def documents(self):
        return self

    def get(self, documentId: str):  # noqa: N803
        return self

    def execute(self) -> dict:
        return self._doc


def test_fetch_todos_extracts_text() -> None:
    doc = {"body": {"content": [
        {"paragraph": {"elements": [{"textRun": {"content": "Email Bob\n"}}]}},
        {"paragraph": {"elements": [{"textRun": {"content": "Review PR\n"}}]}},
    ]}}
    md = fetch_todos(FakeDocs(doc), "doc-1")
    assert "Email Bob" in md and "Review PR" in md
