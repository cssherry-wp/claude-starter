"""Gmail collector: accomplishment notes and the planner email's calendar section."""
from __future__ import annotations

import base64
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, tzinfo
from html import unescape
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from planner.config import GoogleCfg

log = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/spreadsheets.readonly"]

# The planner email lists times in US Eastern; we convert to the host's local zone.
_PLANNER_TZ = "America/New_York"
# Matches a cell like "1:00–2:00 PM ET": captures the start time and its meridiem.
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*(?:[–\-]\s*\d{1,2}:\d{2})?\s*(AM|PM)", re.IGNORECASE)


@dataclass
class CalendarEvent:
    title: str
    start: str
    attendees: list[str]
    raw: str
    time: str = ""
    summary: str = ""


def get_credentials(cfg: GoogleCfg, scopes: list[str]) -> Credentials:
    """Load cached credentials, refreshing or running the consent flow as needed."""
    creds: Credentials | None = None
    if os.path.exists(cfg.token_path):
        creds = Credentials.from_authorized_user_file(cfg.token_path, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cfg.credentials_path, scopes)
            creds = flow.run_local_server(port=0)
        if creds:
            with open(cfg.token_path, "w", encoding="utf-8") as fh:
                fh.write(creds.to_json())
    if creds:
        return creds
    msg = "Failed to obtain credentials"
    raise RuntimeError(msg)


def build_gmail(creds: Credentials) -> Any:
    """Build the Gmail API client."""
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def build_sheets(creds: Credentials) -> Any:
    """Build the Google Sheets API client."""
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _header(message: dict[str, Any], name: str) -> str:
    for h in message.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _list_message_ids(service: Any, q: str) -> list[str]:
    """Return all message ids matching `q`, following nextPageToken to completion."""
    ids: list[str] = []
    page_token: str | None = None
    while True:
        listing = service.users().messages().list(
            userId="me", q=q, pageToken=page_token
        ).execute()
        ids.extend(ref["id"] for ref in listing.get("messages", []))
        page_token = listing.get("nextPageToken")
        if not page_token:
            return ids


def fetch_accomplishments(service: Any, planner_address: str, since: date) -> str:
    """Return Markdown bullets for non-invite messages to the alias since `since`."""
    q = f"to:{planner_address} after:{since.strftime('%Y/%m/%d')} -has:attachment"
    lines: list[str] = []
    for msg_id in _list_message_ids(service, q):
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        subject = _header(msg, "Subject") or "(no subject)"
        snippet = msg.get("snippet", "").strip()
        lines.append(f"- **{subject}** — {snippet}")
    return "\n".join(lines)


def _decode_part(part: dict[str, Any]) -> str:
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


def _to_local_hhmm(time_text: str, event_date: date, local_tz: tzinfo | None = None) -> str:
    """Convert a planner time cell (US Eastern) to a local 'HH:MM' string.

    Args:
        time_text: A cell such as "1:00–2:00 PM ET".
        event_date: The date the event occurs on (for DST-correct conversion).
        local_tz: Target timezone; defaults to the host's local zone.

    Returns:
        Local start time as 'HH:MM', or '' if no time is found.
    """
    match = _TIME_RE.search(time_text)
    if not match:
        return ""
    hour, minute, meridiem = int(match.group(1)), int(match.group(2)), match.group(3).upper()
    if meridiem == "PM" and hour != 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    try:
        eastern = datetime(event_date.year, event_date.month, event_date.day,
                           hour, minute, tzinfo=ZoneInfo(_PLANNER_TZ))
    except ZoneInfoNotFoundError:
        log.warning("tz data for %s unavailable; emitting Eastern wall-clock time", _PLANNER_TZ)
        return f"{hour:02d}:{minute:02d}"
    return eastern.astimezone(local_tz).strftime("%H:%M")


def parse_tomorrow_calendar(body: str, event_date: date,
                            local_tz: tzinfo | None = None) -> list[CalendarEvent]:
    """Extract timed events from the planner email's 'Tomorrow's Calendar' table.

    The table is read as flattened cell lines; each event is anchored on its time
    cell, with the following lines being event title, attendees, then any relevant
    bullets (the bullets column is optional). The trailing 'All-day events' table
    is excluded.

    Args:
        body: Plain-text email body (HTML is flattened to lines before calling).
        event_date: The date the listed events occur on (for time-zone conversion).
        local_tz: Target timezone for the rendered time; defaults to host local.

    Returns:
        Parsed timed events; empty when the section is absent.
    """
    text = body.replace("’", "'")
    start = text.lower().find("tomorrow's calendar")
    if start == -1:
        return []
    section = text[start:]
    cut = section.lower().find("all-day events")
    if cut != -1:
        section = section[:cut]
    # Strip email/blockquote markers ("> ", "> > ") so quoted bodies parse cleanly;
    # lines that are only quote markers collapse to empty and are dropped.
    stripped = (re.sub(r"^\s*(?:>\s?)+", "", ln).strip() for ln in section.splitlines())
    lines = [ln for ln in stripped if ln]
    time_indexes = [i for i, ln in enumerate(lines) if _TIME_RE.search(ln)]
    events: list[CalendarEvent] = []
    for pos, idx in enumerate(time_indexes):
        nxt = time_indexes[pos + 1] if pos + 1 < len(time_indexes) else len(lines)
        cells = lines[idx + 1:nxt]
        if not cells:
            continue
        raw_attendees = re.split(r"[;,]", cells[1]) if len(cells) > 1 else []
        events.append(CalendarEvent(
            title=cells[0],
            start=lines[idx],
            attendees=[a.strip() for a in raw_attendees if a.strip()],
            raw=lines[idx],
            time=_to_local_hhmm(lines[idx], event_date, local_tz),
            summary=" ".join(cells[2:]).strip(),
        ))
    return events


def _walk_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all leaf parts of a (possibly nested multipart) message payload."""
    parts = payload.get("parts")
    if not parts:
        return [payload]
    leaves: list[dict[str, Any]] = []
    for part in parts:
        leaves.extend(_walk_parts(part))
    return leaves


def _strip_html(html: str) -> str:
    """Flatten HTML to text, turning table cells/rows and breaks into newlines."""
    html = re.sub(r"(?i)</(td|th|tr|p|div|li|h[1-6]|table)>", "\n", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    return unescape(re.sub(r"<[^>]+>", "", html))


def _message_text(msg: dict[str, Any]) -> str:
    """Return the message body as text, preferring text/plain over flattened HTML."""
    leaves = _walk_parts(msg.get("payload", {}))
    plain = [p for p in leaves if p.get("mimeType") == "text/plain"]
    if plain:
        return "\n".join(_decode_part(p) for p in plain)
    html = [p for p in leaves if p.get("mimeType") == "text/html"]
    return _strip_html("\n".join(_decode_part(p) for p in html))


def _is_reply_or_forward(subject: str) -> bool:
    """True for reply/forward subjects (e.g. 'Re: …', 'Fwd: …') — not the original."""
    return subject.strip().lower().startswith(("re:", "fwd:", "fw:"))


def fetch_calls(service: Any, planner_address: str, event_date: date) -> list[CalendarEvent]:
    """Return timed events from the most recent original planner email.

    Scans recent emails to the planner alias (newest first), skipping replies and
    forwards (e.g. test '"Re: Daily planner"' threads), and parses the first
    original message containing a 'Tomorrow's Calendar' section.

    Args:
        service: Authenticated Gmail API client.
        planner_address: The planner alias the email is sent to.
        event_date: The date the listed events occur on (for time-zone conversion).

    Returns:
        Parsed timed events, or an empty list if none are found.
    """
    for msg_id in _list_message_ids(service, f"to:{planner_address}"):
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        if _is_reply_or_forward(_header(msg, "Subject")):
            continue
        events = parse_tomorrow_calendar(_message_text(msg), event_date)
        if events:
            return events
    return []
