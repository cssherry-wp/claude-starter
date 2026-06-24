"""Match calendar attendees to the People template's hashtags."""
from __future__ import annotations

import re


def parse_people_tags(text: str) -> list[str]:
    """Return the hashtags listed in the People template.

    Args:
        text: Contents of the People template (one tag per line; section
            labels and blank lines are ignored).

    Returns:
        The '#category/first_last' tags, in template order.
    """
    return [line.strip() for line in text.splitlines() if line.strip().startswith("#")]


def _name_tokens(name: str) -> set[str]:
    """Return the lowercase alphanumeric tokens of a person's name."""
    return {token for token in re.split(r"[^a-z0-9]+", name.lower()) if token}


def match_people_tags(attendees: list[str], people_tags: list[str]) -> list[str]:
    """Return People-template tags whose name slug matches any attendee.

    A tag '#category/first_last' matches an attendee when every
    underscore-separated token of its slug appears in that attendee's name
    tokens (so 'ray_rouleau' matches "Ray Rouleau" and 'sherry' matches
    "Sherry Zhou"). Results are deduped and kept in template order.

    Args:
        attendees: Attendee name strings from a calendar event.
        people_tags: Tags parsed from the People template.

    Returns:
        Matching tags, deduplicated, in template order.
    """
    attendee_tokens = [_name_tokens(a) for a in attendees]
    matched: list[str] = []
    for tag in people_tags:
        slug_tokens = {token for token in tag.rsplit("/", 1)[-1].split("_") if token}
        if not slug_tokens:
            continue
        if any(slug_tokens <= tokens for tokens in attendee_tokens) and tag not in matched:
            matched.append(tag)
    return matched
