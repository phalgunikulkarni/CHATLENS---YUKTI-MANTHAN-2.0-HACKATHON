"""Add Calendar Agent (functional agent id="add_calendar").

Turns a CONFIRMED user action into a calendar event via the existing
CalendarService (P2S4). It does NOT parse free chat text and does NOT mutate
anything unless the caller explicitly confirms — confirmation-before-mutation
is enforced here as a backstop even though the UI also gates it.

Params (via AgentContext.params):
  confirmed:    bool  (REQUIRED true to create; otherwise returns a preview)
  title, date, start_time            (required for creation)
  end_time, timezone, participants, reminder   (optional)

Account isolation: uses context.account_id (resolved by the backend from the
X-Account-Id header). A client-supplied account is never trusted here.
"""
from __future__ import annotations

from typing import Optional

from .contracts import Agent, AgentContext, AgentResult

# Import lazily inside run() to keep agent import cheap and avoid hard coupling
# at module import time.


class AddCalendarAgent(Agent):
    id = "add_calendar"
    description = "Create a calendar event from a confirmed user action (via CalendarService)."

    def __init__(self, service=None) -> None:
        self._service = service  # injectable for tests

    def _svc(self):
        if self._service is None:
            from calendar_tasks.calendar_service import CalendarService
            self._service = CalendarService()
        return self._service

    def run(self, context: AgentContext) -> AgentResult:
        params = context.params or {}
        account_id = context.account_id
        if not account_id:
            return AgentResult.failure(
                self.id, error="no_account",
                message="No account context; cannot create an event.",
            )

        title = (params.get("title") or "").strip()
        date = (params.get("date") or "").strip()
        start_time = (params.get("start_time") or "").strip()

        # Confirmation-before-mutation: without explicit confirmation we only
        # echo back a preview of what WOULD be created (no storage writes).
        if not bool(params.get("confirmed")):
            return AgentResult.success(
                self.id, message="Confirmation required before creating the event.",
                data={
                    "confirmed": False,
                    "preview": {
                        "title": title, "date": date, "start_time": start_time,
                        "end_time": params.get("end_time"),
                        "timezone": params.get("timezone"),
                        "participants": params.get("participants", ""),
                        "reminder": params.get("reminder"),
                    },
                },
                metadata={"requires_confirmation": True},
            )

        try:
            from calendar_tasks.validation import ValidationError
            from calendar_tasks.calendar_service import CalendarServiceError
        except Exception as exc:  # noqa: BLE001
            return AgentResult.failure(self.id, error=f"import_error: {exc}",
                                       message="Calendar service is unavailable.")

        try:
            event = self._svc().create_event(
                account_id=account_id,
                title=title,
                date=date,
                start_time=start_time,
                end_time=params.get("end_time"),
                timezone=params.get("timezone"),
                participants=params.get("participants"),
                reminder=params.get("reminder"),
            )
        except ValidationError as exc:
            return AgentResult.failure(self.id, error=f"validation: {exc}",
                                       message=str(exc), data={"confirmed": True})
        except CalendarServiceError:
            return AgentResult.failure(self.id, error="calendar_error",
                                       message="Could not create the event.")

        reminder_note = " Reminder scheduled." if event.reminder else ""
        return AgentResult.success(
            self.id, message=f"Added to Calendar.{reminder_note}",
            data={"confirmed": True, "event": event.to_dict()},
            evidence=[{"type": "calendar_event", "id": event.id}],
            metadata={"reminder_scheduled": bool(event.reminder)},
        )
