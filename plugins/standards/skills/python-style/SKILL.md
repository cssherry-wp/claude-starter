---
name: python-style
description: Python coding standards. Use when writing, editing, or reviewing Python (.py) files — covers AI-prone mistakes, Google-style docstrings, type annotations, and testing.
---

# Python Coding Guidelines

*ruff handles all formatting (Black), imports (isort), naming, and linting (PEP-8 compliance). mypy checks type correctness. See the `general-coding-guidelines` skill for general rules.*

## AI-Prone Mistakes — Always Avoid

- **Never use `eval()` or `exec()`** — prefer safe alternatives
- **Prefer f-strings** over `.format()` or `%` formatting, but keep them readable
- **Functions longer than 40 lines?** Extract. (See `general-coding-guidelines`.)

## Docstrings (AI Gets This Wrong Often)

Use **Google-style** docstrings for all public functions and classes. Be consistent within the project.

```python
def process_data(input: str, limit: int = 10) -> list[dict]:
    """Process input data with optional limit.

    Args:
        input: The input string to process.
        limit: Maximum number of results to return. Defaults to 10.

    Returns:
        List of processed result dicts.

    Raises:
        ValueError: If limit is negative.
    """
```

## Type Annotations (New Files)

- Use type annotations for **all** function signatures and class attributes in new files
- Match existing style in the file if it already uses hints
- Don't annotate obviously-inferable locals (`x = []` — no annotation needed)

## Testing

- **Co-locate tests with source**: `test_foo.py` next to `foo.py` (see `general-coding-guidelines`).
- Cover happy path, edge cases, and failure modes.
