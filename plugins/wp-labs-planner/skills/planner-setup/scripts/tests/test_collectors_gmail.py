from __future__ import annotations

from datetime import date, datetime, timezone

from zoneinfo import ZoneInfo

from planner.collectors.gmail import (
    CalendarEvent, _event_is_future, _to_local_hhmm, fetch_accomplishments, fetch_calls,
    parse_ics, parse_tomorrow_calendar,
)

_PLANNER_BODY = """Chatbot-dashboard docs

Description

Sherry follow-up

TODO 1


Tomorrow's Calendar

Time
Event
Attendees
Relevant bullets

1:00–2:00 PM ET
Demo Hour
Sherry Zhou; organized by PLACEHOLDER
Likely topics to bring: Claude starter/plugin consolidation, GitHub PR review skill.



All-day events

Event
Date / span
Attendees

Sherry OOO
Ongoing all-day event
Sherry only / no listed attendees.
"""


class FakeMessages:
    def __init__(self, listing: dict, messages: dict) -> None:
        self._listing, self._messages = listing, messages

    def list(self, userId: str, q: str, pageToken: str | None = None):  # noqa: N803 (Google API kwargs)
        self._last_q = q
        return _Exec(self._listing)

    def get(self, userId: str, id: str, format: str = "full"):  # noqa: N803,A002
        return _Exec(self._messages[id])


class _Exec:
    def __init__(self, value: dict) -> None:
        self._value = value

    def execute(self) -> dict:
        return self._value


class FakeService:
    def __init__(self, listing: dict, messages: dict) -> None:
        self._m = FakeMessages(listing, messages)

    def users(self):
        return self

    def messages(self):
        return self._m


def test_fetch_accomplishments_returns_markdown() -> None:
    listing = {"messages": [{"id": "m1"}]}
    messages = {"m1": {"snippet": "Shipped the thing",
                       "payload": {"headers": [{"name": "Subject", "value": "Done: shipping"}]}}}
    svc = FakeService(listing, messages)
    md = fetch_accomplishments(svc, "s+planner@x.com", date(2026, 6, 22))
    assert "Done: shipping" in md
    assert "Shipped the thing" in md


def test_parse_ics_extracts_event() -> None:
    ics = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Sync with Meg\n"
           "DTSTART:20260625T150000Z\nATTENDEE;CN=Meg:mailto:meg@x.com\nEND:VEVENT\nEND:VCALENDAR")
    ev = parse_ics(ics)
    assert isinstance(ev, CalendarEvent)
    assert ev.title == "Sync with Meg"
    assert ev.start == "20260625T150000Z"
    assert "meg@x.com" in ev.attendees


def test_parse_ics_all_day_returns_none() -> None:
    ics = "BEGIN:VEVENT\nSUMMARY:Holiday\nDTSTART;VALUE=DATE:20260625\nEND:VEVENT"
    assert parse_ics(ics) is None


def test_to_local_hhmm_converts_et_to_local() -> None:
    la = ZoneInfo("America/Los_Angeles")
    # 1:00 PM EDT on 2026-06-24 == 10:00 PDT
    assert _to_local_hhmm("1:00–2:00 PM ET", date(2026, 6, 24), la) == "10:00"
    assert _to_local_hhmm("9:30 AM ET", date(2026, 6, 24), ZoneInfo("America/New_York")) == "09:30"


def test_to_local_hhmm_no_time_returns_empty() -> None:
    assert _to_local_hhmm("All day", date(2026, 6, 24), ZoneInfo("UTC")) == ""


def test_parse_tomorrow_calendar_extracts_timed_event_excluding_all_day() -> None:
    events = parse_tomorrow_calendar(_PLANNER_BODY, date(2026, 6, 24),
                                     ZoneInfo("America/Los_Angeles"))
    assert len(events) == 1  # the all-day "Sherry OOO" event is excluded
    ev = events[0]
    assert ev.title == "Demo Hour"
    assert ev.time == "10:00"
    assert "Sherry Zhou" in ev.attendees
    assert "Likely topics to bring" in ev.summary


def test_parse_tomorrow_calendar_handles_three_column_table() -> None:
    """The Relevant-bullets column is optional; title + time still parse."""
    body = ("Tomorrow's Calendar\nTime\nEvent\nAttendees\n"
            "1:00–2:00 PM ET\nDemo Hour\nSherry Zhou\nAll-day events\n")
    events = parse_tomorrow_calendar(body, date(2026, 6, 24), ZoneInfo("America/Los_Angeles"))
    assert len(events) == 1
    assert events[0].title == "Demo Hour" and events[0].time == "10:00"
    assert events[0].summary == ""


def test_parse_tomorrow_calendar_absent_section_returns_empty() -> None:
    assert parse_tomorrow_calendar("nothing here", date(2026, 6, 24)) == []


def test_fetch_calls_parses_planner_email_body() -> None:
    import base64
    data = base64.urlsafe_b64encode(_PLANNER_BODY.encode()).decode()
    listing = {"messages": [{"id": "m1"}]}
    messages = {"m1": {"payload": {"mimeType": "multipart/alternative",
                                   "parts": [{"mimeType": "text/plain", "body": {"data": data}}]}}}
    svc = FakeService(listing, messages)
    events = fetch_calls(svc, "s+planner@x.com", date(2026, 6, 24))
    assert [e.title for e in events] == ["Demo Hour"]


_NOW = datetime(2026, 6, 23, tzinfo=timezone.utc)


def test_event_is_future_future_utc() -> None:
    assert _event_is_future("20990101T120000Z", _NOW) is True


def test_event_is_future_past_utc() -> None:
    assert _event_is_future("20000101T120000Z", _NOW) is False


def test_event_is_future_unparseable_is_lenient() -> None:
    assert _event_is_future("garbage", _NOW) is True


def test_gmail_scopes_use_spreadsheets() -> None:
    from planner.collectors.gmail import GMAIL_SCOPES
    assert any("spreadsheets.readonly" in s for s in GMAIL_SCOPES)
    assert not any("documents.readonly" in s for s in GMAIL_SCOPES)


def test_build_sheets_exists() -> None:
    from planner.collectors import gmail
    assert callable(gmail.build_sheets)


class _PagedMessages(FakeMessages):
    def list(self, userId: str, q: str, pageToken: str | None = None):  # noqa: N803
        if pageToken is None:
            return _Exec({"messages": [{"id": "m1"}], "nextPageToken": "p2"})
        return _Exec({"messages": [{"id": "m2"}]})


def test_fetch_accomplishments_follows_pagination() -> None:
    messages = {
        "m1": {"snippet": "first", "payload": {"headers": [{"name": "Subject", "value": "One"}]}},
        "m2": {"snippet": "second", "payload": {"headers": [{"name": "Subject", "value": "Two"}]}},
    }
    svc = FakeService({}, messages)
    svc._m = _PagedMessages({}, messages)
    md = fetch_accomplishments(svc, "s+planner@x.com", date(2026, 6, 22))
    assert "One" in md and "Two" in md  # second page not dropped
