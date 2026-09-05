"""Reminder Agent (functional agent id="reminder").

Create / list / cancel reminders via the isolated ReminderService (APScheduler).
Driven entirely by AgentContext.params; never raises to the orchestrator (bad
input -> AgentResult.failure).

params:
  operation: "create" | "list" | "cancel"
  message:   str   (create)
  run_at:    ISO-8601 str or epoch seconds (create)
  reminder_id: str (cancel; optional on create)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .contracts import Agent, AgentContext, AgentResult, AgentError
from .reminder_service import ReminderService

# Shared, lazily-created service so all invocations use one scheduler.
_SERVICE: Optional[ReminderService] = None


def _service() -> ReminderService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ReminderService()
    return _SERVICE


def _parse_run_at(value) -> datetime:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise AgentError("run_at is required")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    # Accept trailing 'Z' as UTC.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception as exc:
        raise AgentError(f"invalid run_at {value!r}: {exc}")


class ReminderAgent(Agent):
    id = "reminder"
    description = "Create, list, and cancel time-based reminders (local APScheduler)."

    def __init__(self, service: Optional[ReminderService] = None) -> None:
        # Allow injection for tests; default to the shared process service.
        self._svc = service

    def _svc_or_default(self) -> ReminderService:
        return self._svc if self._svc is not None else _service()

    def run(self, context: AgentContext) -> AgentResult:
        params = context.params or {}
        op = (params.get("operation") or "").strip().lower()
        svc = self._svc_or_default()

        if op == "create":
            try:
                run_at = _parse_run_at(params.get("run_at"))
                rem = svc.create(
                    message=params.get("message", ""),
                    run_at=run_at,
                    reminder_id=params.get("reminder_id"),
                )
            except (AgentError, ValueError) as exc:
                return AgentResult.failure(self.id, error=str(exc),
                                           message="Could not create the reminder.")
            return AgentResult.success(
                self.id, message="Reminder scheduled.",
                data={"reminder": rem.to_dict()},
                metadata={"operation": "create"},
            )

        if op == "list":
            reminders = [r.to_dict() for r in svc.list()]
            return AgentResult.success(
                self.id, message=f"{len(reminders)} reminder(s).",
                data={"reminders": reminders},
                metadata={"operation": "list"},
            )

        if op == "cancel":
            try:
                rem = svc.cancel(params.get("reminder_id"))
            except (AgentError, ValueError) as exc:
                return AgentResult.failure(self.id, error=str(exc),
                                           message="Could not cancel the reminder.")
            return AgentResult.success(
                self.id, message="Reminder cancelled.",
                data={"reminder": rem.to_dict()},
                metadata={"operation": "cancel"},
            )

        return AgentResult.failure(
            self.id, error=f"unknown operation {op!r}",
            message="operation must be one of: create, list, cancel.",
        )
