from __future__ import annotations

from datetime import date, datetime, timezone

from planner.collectors.gmail import (
    CalendarEvent, _event_is_future, fetch_accomplishments, parse_ics,
)


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


_NOW = datetime(2026, 6, 23, tzinfo=timezone.utc)


def test_event_is_future_future_utc() -> None:
    assert _event_is_future("20990101T120000Z", _NOW) is True


def test_event_is_future_past_utc() -> None:
    assert _event_is_future("20000101T120000Z", _NOW) is False


def test_event_is_future_unparseable_is_lenient() -> None:
    assert _event_is_future("garbage", _NOW) is True


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
