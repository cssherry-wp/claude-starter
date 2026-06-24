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


def people_bullets(attendees: list[str], tags: list[str]) -> list[str]:
    """Return one bullet per attendee: a matching People tag, else the raw name.

    Attendees that resolve to People-template tags are represented by those tags;
    unmatched attendees (e.g. prose like "and others") are kept as plain text.
    Deduped, in first-seen order.

    Args:
        attendees: Attendee name strings from a calendar event.
        tags: The full set of People tags (existing plus any just added).

    Returns:
        Tag and/or plain-text entries, deduplicated, in attendee order.
    """
    bullets: list[str] = []
    for attendee in attendees:
        name = attendee.strip()
        if not name:
            continue
        for entry in match_people_tags([name], tags) or [name]:
            if entry not in bullets:
                bullets.append(entry)
    return bullets


def _looks_like_name(text: str) -> bool:
    """Return True for a plausible "First Last" person name (2-3 capitalized words)."""
    tokens = text.split()
    return 2 <= len(tokens) <= 3 and all(t.isalpha() and t[0].isupper() for t in tokens)


def new_person_tags(attendees: list[str], existing_tags: list[str], prefix: str) -> list[str]:
    """Return new '#{prefix}/{slug}' tags for name-like attendees not already known.

    Skips attendees that don't look like a person name (e.g. "organized by
    PLACEHOLDER") and those already covered by an existing tag. Deduped, in
    first-seen order.

    Args:
        attendees: Attendee name strings from calendar events.
        existing_tags: Tags already present in the People template.
        prefix: Category prefix for new tags (the part before '/').

    Returns:
        New tags to append to the People template.
    """
    new: list[str] = []
    for attendee in attendees:
        name = attendee.strip()
        if not _looks_like_name(name) or match_people_tags([name], existing_tags):
            continue
        tag = f"#{prefix}/{'_'.join(name.split()).lower()}"
        if tag not in new:
            new.append(tag)
    return new
