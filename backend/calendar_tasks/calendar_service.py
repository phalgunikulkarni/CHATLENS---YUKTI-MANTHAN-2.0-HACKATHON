"""Calendar service: CalDAV (Radicale) engine with a durable local fallback.

Design goal (per P2S4): the CalendarService can later point at a locally-hosted
Radicale/CalDAV server WITHOUT changing the frontend HTTP contract. Selection:

  - CHATLENS_CALDAV_URL set  -> CalDavCalendarStore (python-caldav + icalendar)
  - otherwise (default/dev)  -> LocalCalendarStore (durable per-account JSON)

Account isolation:
  - CalDAV: one calendar collection per account (derived from account_id).
  - Local: one JSON file per account under the calendar data dir.

No credentials are hard-coded or exposed to the frontend. Times preserve the
user's IANA timezone (no silent UTC reinterpretation of local wall-clock time).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from . import config
from .models import CalendarEvent
from .validation import (
    ValidationError,
    valid_date,
    valid_time,
    optional_time,
    valid_timezone,
    require_nonempty,
    ensure_end_after_start,
)

_ACCOUNT_RE = __import__("re").compile(r"^acct-[0-9a-f]+$")


class CalendarServiceError(Exception):
    """Calendar backend failure (-> HTTP 500 with a safe message)."""


def _check_account(account_id: str) -> str:
    if not account_id or not _ACCOUNT_RE.match(account_id):
        raise CalendarServiceError("invalid account")
    return account_id


# ---------------------------------------------------------------------------
# Local durable store (default). Real user data persisted to disk per account.
# ---------------------------------------------------------------------------
class LocalCalendarStore:
    def __init__(self, data_dir: Optional[str] = None) -> None:
        self._dir = data_dir or config.calendar_data_dir()
        os.makedirs(self._dir, exist_ok=True)

    def _path(self, account_id: str) -> str:
        return os.path.join(self._dir, f"{_check_account(account_id)}.json")

    def _load(self, account_id: str) -> List[Dict[str, Any]]:
        p = self._path(account_id)
        if not os.path.isfile(p):
            return []
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, account_id: str, rows: List[Dict[str, Any]]) -> None:
        p = self._path(account_id)
        tmp = f"{p}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(rows, f)
            os.replace(tmp, p)  # atomic
        except OSError as exc:
            raise CalendarServiceError("could not persist event") from exc

    def list_events(self, account_id: str) -> List[CalendarEvent]:
        return [CalendarEvent(**r) for r in self._load(account_id)]

    def create_event(self, account_id: str, event: CalendarEvent) -> CalendarEvent:
        rows = self._load(account_id)
        rows.append(event.to_dict())
        self._save(account_id, rows)
        return event

    def delete_event(self, account_id: str, event_id: str) -> None:
        rows = self._load(account_id)
        next_rows = [r for r in rows if r.get("id") != event_id]
        if len(next_rows) == len(rows):
            raise ValidationError("event not found")
        self._save(account_id, next_rows)


# ---------------------------------------------------------------------------
# CalDAV store (used when CHATLENS_CALDAV_URL is configured).
# ---------------------------------------------------------------------------
class CalDavCalendarStore:
    """python-caldav + icalendar backend. One collection per account.

    Frontend fields are preserved via iCalendar properties + X- fields so the
    exact date/time/timezone/participants/reminder round-trip losslessly.
    """

    def __init__(self) -> None:
        if not config.caldav_configured():
            raise CalendarServiceError("CalDAV is not configured")

    def _principal(self):
        import caldav
        client = caldav.DAVClient(
            url=config.CALDAV_URL,
            username=config.CALDAV_USERNAME or None,
            password=config.CALDAV_PASSWORD or None,
        )
        return client.principal()

    def _collection(self, account_id: str):
        # One calendar per account; name derived ONLY from the validated account.
        name = f"chatlens-{_check_account(account_id)}"
        principal = self._principal()
        try:
            return principal.calendar(name=name)
        except Exception:
            return principal.make_calendar(name=name)

    def list_events(self, account_id: str) -> List[CalendarEvent]:
        try:
            cal = self._collection(account_id)
            out: List[CalendarEvent] = []
            for ev in cal.events():
                parsed = _ical_to_event(ev.data)
                if parsed:
                    out.append(parsed)
            return out
        except CalendarServiceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CalendarServiceError("could not read calendar") from exc

    def create_event(self, account_id: str, event: CalendarEvent) -> CalendarEvent:
        try:
            cal = self._collection(account_id)
            cal.save_event(_event_to_ical(event))
            return event
        except Exception as exc:  # noqa: BLE001
            raise CalendarServiceError("could not create event") from exc

    def delete_event(self, account_id: str, event_id: str) -> None:
        try:
            cal = self._collection(account_id)
            for ev in cal.events():
                parsed = _ical_to_event(ev.data)
                if parsed and parsed.id == event_id:
                    ev.delete()
                    return
            raise ValidationError("event not found")
        except (ValidationError, CalendarServiceError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise CalendarServiceError("could not delete event") from exc


def _event_to_ical(event: CalendarEvent) -> str:
    from icalendar import Calendar, Event as IEvent
    from .validation import aware_datetime
    cal = Calendar()
    cal.add("prodid", "-//ChatLens//Calendar//EN")
    cal.add("version", "2.0")
    ie = IEvent()
    ie.add("uid", event.id)
    ie.add("summary", event.title)
    ie.add("dtstart", aware_datetime(event.date, event.start_time, event.timezone))
    if event.end_time:
        ie.add("dtend", aware_datetime(event.date, event.end_time, event.timezone))
    if event.participants:
        ie.add("description", event.participants)
    # Preserve exact frontend fields for lossless round-trip.
    ie.add("x-chatlens-date", event.date)
    ie.add("x-chatlens-start", event.start_time)
    ie.add("x-chatlens-end", event.end_time or "")
    ie.add("x-chatlens-tz", event.timezone)
    ie.add("x-chatlens-reminder", event.reminder or "")
    ie.add("x-chatlens-created", str(event.created_at))
    cal.add_component(ie)
    return cal.to_ical().decode("utf-8")


def _ical_to_event(ical_text: str) -> Optional[CalendarEvent]:
    from icalendar import Calendar
    try:
        cal = Calendar.from_ical(ical_text)
    except Exception:  # noqa: BLE001
        return None
    for comp in cal.walk("VEVENT"):
        def g(key, default=""):
            v = comp.get(key)
            return str(v) if v is not None else default
        created = g("x-chatlens-created", "0")
        try:
            created_at = int(created)
        except ValueError:
            created_at = 0
        return CalendarEvent(
            id=g("uid"),
            title=g("summary"),
            date=g("x-chatlens-date"),
            start_time=g("x-chatlens-start"),
            end_time=(g("x-chatlens-end") or None),
            timezone=g("x-chatlens-tz", "UTC"),
            participants=g("description"),
            reminder=(g("x-chatlens-reminder") or None),
            created_at=created_at,
        )
    return None


# ---------------------------------------------------------------------------
# Public service: validates input, builds the event, delegates to the store.
# ---------------------------------------------------------------------------
class CalendarService:
    def __init__(self, store=None) -> None:
        if store is not None:
            self._store = store
        elif config.caldav_configured():
            self._store = CalDavCalendarStore()
        else:
            self._store = LocalCalendarStore()

    @property
    def backend(self) -> str:
        return "caldav" if isinstance(self._store, CalDavCalendarStore) else "local"

    def list_events(self, account_id: str) -> List[CalendarEvent]:
        return self._store.list_events(_check_account(account_id))

    def create_event(
        self,
        account_id: str,
        title: str,
        date: str,
        start_time: str,
        end_time: Optional[str],
        timezone: Optional[str],
        participants: Optional[str],
        reminder: Optional[str],
    ) -> CalendarEvent:
        _check_account(account_id)
        title = require_nonempty(title, "title")
        date = valid_date(date, "date")
        start_time = valid_time(start_time, "start_time")
        end_time = optional_time(end_time, "end_time")
        ensure_end_after_start(start_time, end_time)
        tz = valid_timezone(timezone)
        event = CalendarEvent(
            id=f"evt-{uuid.uuid4().hex}",
            title=title,
            date=date,
            start_time=start_time,
            end_time=end_time,
            timezone=tz,
            participants=(participants or "").strip(),
            reminder=(reminder.strip() if reminder and reminder.strip() else None),
            created_at=int(time.time() * 1000),
        )
        created = self._store.create_event(account_id, event)

        # Optional in-app reminder seam (best-effort; does not fail creation).
        if created.reminder:
            try:
                from .reminders import schedule_in_app_reminder
                from .validation import aware_datetime
                run_at = aware_datetime(created.date, created.start_time, created.timezone)
                schedule_in_app_reminder(f"cal-{created.id}", f"Event: {created.title}", run_at)
            except Exception:  # noqa: BLE001 - reminders are best-effort
                pass
        return created

    def delete_event(self, account_id: str, event_id: str) -> None:
        _check_account(account_id)
        if not event_id or not event_id.strip():
            raise ValidationError("invalid event id")
        self._store.delete_event(account_id, event_id)
