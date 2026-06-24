"""Gmail collector: accomplishment notes and calendar-invite calls."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from planner.config import GoogleCfg

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/documents.readonly"]


@dataclass
class CalendarEvent:
    title: str
    start: str
    attendees: list[str]
    raw: str


def _event_is_future(start: str, now: datetime) -> bool:
    """True if an ICS DTSTART (e.g. '20260625T150000Z') is at/after `now`.

    Args:
        start: DTSTART string from an ICS VEVENT.
        now: Timezone-aware UTC datetime representing the current moment.

    Returns:
        True if the event is in the future (or unparseable), False if in the past.
    """
    try:
        dt = datetime.strptime(start, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt >= now
    except ValueError:
        pass
    try:
        dt_naive = datetime.strptime(start, "%Y%m%dT%H%M%S")
        return dt_naive >= now.replace(tzinfo=None)
    except ValueError:
        return True


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


def build_docs(creds: Credentials) -> Any:
    """Build the Google Docs API client."""
    return build("docs", "v1", credentials=creds, cache_discovery=False)


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


def parse_ics(text: str) -> CalendarEvent | None:
    """Parse the first VEVENT; return None for all-day (DATE-only) events."""
    title, start, attendees = "", "", []
    for line in text.splitlines():
        if line.startswith("SUMMARY:"):
            title = line[len("SUMMARY:"):].strip()
        elif line.startswith("DTSTART;VALUE=DATE:"):
            return None
        elif line.startswith("DTSTART"):
            start = line.split(":", 1)[1].strip()
        elif line.startswith("ATTENDEE"):
            if "mailto:" in line:
                attendees.append(line.split("mailto:", 1)[1].strip())
    if not title or not start:
        return None
    return CalendarEvent(title=title, start=start, attendees=attendees, raw=text)


def _decode_part(part: dict[str, Any]) -> str:
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


def fetch_calls(service: Any, planner_address: str) -> list[CalendarEvent]:
    """Return future-dated timed calendar events from invite emails to the alias."""
    q = f"to:{planner_address} has:attachment"
    events: list[CalendarEvent] = []
    now = datetime.now(timezone.utc)
    for msg_id in _list_message_ids(service, q):
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        for part in msg.get("payload", {}).get("parts", []):
            if part.get("mimeType") == "text/calendar":
                ev = parse_ics(_decode_part(part))
                if ev and _event_is_future(ev.start, now):
                    events.append(ev)
    return events
